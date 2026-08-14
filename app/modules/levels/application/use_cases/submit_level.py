import logging
from datetime import UTC, datetime
from uuid import uuid4

from app.core.exceptions.domain import ConflictError, ForbiddenError
from app.modules.certifications.application.use_cases.evaluate_certification_eligibility import (
    EvaluateCertificationEligibilityUseCase,
)
from app.modules.certifications.domain.repositories.certification_repository import (
    CertificationRepository,
)
from app.modules.levels.application.dto.level_gameplay import LevelSubmitResult
from app.modules.levels.application.use_cases.get_level import LevelNotFoundError
from app.modules.levels.domain.entities.level_session import ExploitStatus, LevelState
from app.modules.levels.domain.repositories.level_repository import LevelRepository
from app.modules.levels.domain.repositories.level_session_repository import LevelSessionRepository
from app.modules.levels.domain.services.level_access import LevelAccessService
from app.modules.progress.application.use_cases.complete_level import CompleteLevelUseCase
from app.modules.progress.domain.repositories.progress_repository import ProgressRepository
from app.modules.submissions.domain.entities.submission import Submission, SubmissionStatus
from app.modules.submissions.domain.repositories.submission_repository import SubmissionRepository
from app.modules.submissions.domain.services.verification_engine import VerificationEngine
from app.modules.users.domain.repositories.user_repository import UserRepository
from app.shared.blockchain import BlockchainClientInterface, BlockchainTransaction
from app.shared.events.event_bus import DomainEvent, EventPublisher

logger = logging.getLogger(__name__)


class LevelNotStartedError(ConflictError):
    code = "LEVEL_NOT_STARTED"


class InvalidSubmissionError(ForbiddenError):
    code = "INVALID_SUBMISSION"


class LevelSetupRequiredError(ConflictError):
    code = "LEVEL_SETUP_REQUIRED"


class SubmitLevelUseCase:
    def __init__(
        self,
        levels: LevelRepository,
        sessions: LevelSessionRepository,
        submissions: SubmissionRepository,
        progress: ProgressRepository,
        users: UserRepository,
        certifications: CertificationRepository,
        access: LevelAccessService,
        verification: VerificationEngine,
        events: EventPublisher,
        blockchain: BlockchainClientInterface | None = None,
    ) -> None:
        self._levels = levels
        self._sessions = sessions
        self._submissions = submissions
        self._progress = progress
        self._users = users
        self._certifications = certifications
        self._access = access
        self._verification = verification
        self._events = events
        self._blockchain = blockchain

    async def execute(self, user_id: str, level_id: str, payload: dict) -> LevelSubmitResult:
        level = await self._levels.get_by_id(level_id)
        if level is None:
            raise LevelNotFoundError("Level not found")

        latest_session = await self._sessions.get_latest(user_id, level_id)
        state, _ = await self._access.state_for(user_id, level, latest_session)
        if state == LevelState.LOCKED:
            raise InvalidSubmissionError("Level is locked")

        payload = dict(payload)
        tx_signature = payload.get("transaction_signature")
        wallet_address = payload.get("wallet_address")
        session = await self._sessions.get_active(user_id, level_id)
        if session is None:
            idempotent_result = await self._idempotent_completed_result(
                user_id,
                level,
                latest_session,
                tx_signature if isinstance(tx_signature, str) else None,
            )
            if idempotent_result is not None:
                return idempotent_result
            raise LevelNotStartedError("Start the level before submitting proof")

        if level.deployment_info.get("execution", {}).get("enabled") is True:
            if not session.challenge_context:
                raise LevelSetupRequiredError("Run level setup before submitting proof")

        if isinstance(tx_signature, str):
            existing = await self._submissions.get_by_tx_signature(tx_signature)
            if existing is not None:
                raise InvalidSubmissionError("Transaction signature was already submitted")
            payload = await self._attach_onchain_proof(payload)
            payload = _attach_derived_token_balances(payload, session.challenge_context)

        attempt_number = await self._submissions.count_for_user_level(user_id, level_id) + 1
        submission = await self._submissions.create(
            Submission(
                id=str(uuid4()),
                user_id=user_id,
                level_id=level_id,
                session_id=session.id,
                attempt_number=attempt_number,
                payload=payload,
                tx_signature=tx_signature if isinstance(tx_signature, str) else None,
                wallet_address=wallet_address if isinstance(wallet_address, str) else None,
                status=SubmissionStatus.PENDING,
                verification_message="Verification pending",
            )
        )

        verification_result = self._verification.verify(
            _runtime_verification_config(level.verification_config, session),
            _payload_with_session_context(payload, session),
        )
        logger.info(
            "level_verification_completed",
            extra={
                "user_id": user_id,
                "level_id": level_id,
                "verified": verification_result.verified,
                "attempt_number": attempt_number,
            },
        )
        submission.status = (
            SubmissionStatus.VERIFIED if verification_result.verified else SubmissionStatus.REJECTED
        )
        submission.verification_message = verification_result.message
        submission.verification_result = verification_result.to_dict()
        submission = await self._submissions.update(submission)

        now = datetime.now(UTC)
        session.attempt_count += 1
        session.last_submitted_at = now
        if isinstance(tx_signature, str):
            session.tx_signature = tx_signature
        progress = None
        certification = None
        unlocked_next_level_id = None

        if verification_result.verified:
            session.state = LevelState.COMPLETED
            session.exploit_status = ExploitStatus.VERIFIED
            session.completed_at = now
            session.verified_at = now
            progress = await CompleteLevelUseCase(
                self._progress, self._levels, self._users, self._events
            ).execute(user_id, level_id)
            next_level = await self._levels.get_by_order(level.order + 1)
            unlocked_next_level_id = next_level.id if next_level else None
            logger.info(
                "progression_updated",
                extra={
                    "user_id": user_id,
                    "level_id": level_id,
                    "xp_awarded": progress.xp_awarded,
                    "unlocked_next_level_id": unlocked_next_level_id,
                },
            )
            certification = await EvaluateCertificationEligibilityUseCase(
                self._certifications, self._levels, self._progress, self._events
            ).execute(user_id)
        else:
            session.state = LevelState.FAILED
            session.exploit_status = ExploitStatus.FAILED

        session = await self._sessions.update(session)
        await self._events.publish(
            DomainEvent(
                name="submission_verified"
                if verification_result.verified
                else "submission_rejected",
                payload={
                    "submission_id": submission.id,
                    "user_id": user_id,
                    "level_id": level_id,
                },
            )
        )
        return LevelSubmitResult(
            level=level,
            session=session,
            submission=submission,
            progress=progress,
            unlocked_next_level_id=unlocked_next_level_id,
            certification=certification,
        )

    async def _idempotent_completed_result(
        self,
        user_id: str,
        level,
        latest_session,
        tx_signature: str | None,
    ) -> LevelSubmitResult | None:
        if latest_session is None or latest_session.state != LevelState.COMPLETED:
            return None
        if not tx_signature or latest_session.tx_signature != tx_signature:
            return None
        existing = await self._submissions.get_by_tx_signature(tx_signature)
        if (
            existing is None
            or existing.user_id != user_id
            or existing.level_id != level.id
            or existing.session_id != latest_session.id
        ):
            return None
        progress = await self._progress.get_for_user_level(user_id, level.id)
        certification = await EvaluateCertificationEligibilityUseCase(
            self._certifications, self._levels, self._progress, self._events
        ).execute(user_id)
        next_level = await self._levels.get_by_order(level.order + 1)
        return LevelSubmitResult(
            level=level,
            session=latest_session,
            submission=existing,
            progress=progress,
            unlocked_next_level_id=next_level.id if next_level else None,
            certification=certification,
        )

    async def _attach_onchain_proof(self, payload: dict) -> dict:
        if self._blockchain is None:
            return payload
        signature = payload.get("transaction_signature")
        if not isinstance(signature, str):
            return payload
        try:
            transaction = await self._blockchain.get_transaction(signature)
        except RuntimeError:
            transaction = None
        payload = dict(payload)
        payload["onchain_transaction"] = (
            transaction.to_proof()
            if transaction is not None
            else BlockchainTransaction(
                signature=signature,
                network="devnet",
                exists=False,
                succeeded=False,
            ).to_proof()
        )
        payload["transaction_succeeded"] = payload["onchain_transaction"]["succeeded"]
        return payload


def _payload_with_session_context(payload: dict, session) -> dict:
    enriched = dict(payload)
    enriched["challenge_context"] = session.challenge_context
    return enriched


def _runtime_verification_config(config: dict, session) -> dict:
    checks = []
    for check in config.get("checks", []):
        check = dict(check)
        if check.get("type") == "session_binding":
            check["expected_session_id"] = session.id
            check["expected_wallet_address"] = session.wallet_address
        checks.append(check)
    return {**config, "checks": checks}


def _attach_derived_token_balances(payload: dict, challenge_context: dict) -> dict:
    onchain = payload.get("onchain_transaction")
    if not isinstance(onchain, dict) or not isinstance(challenge_context, dict):
        return payload
    deltas = onchain.get("token_balance_deltas") or {}
    attacker_account = challenge_context.get("attacker_token_account")
    vault_account = challenge_context.get("fake_vault")
    if attacker_account in deltas or vault_account in deltas:
        payload = dict(payload)
        payload["token_balances"] = {
            "attacker_token_delta": deltas.get(attacker_account, 0),
            "vault_delta": deltas.get(vault_account, 0),
        }
    return payload
