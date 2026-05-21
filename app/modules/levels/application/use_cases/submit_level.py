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
from app.modules.levels.domain.entities.level_session import LevelState
from app.modules.levels.domain.repositories.level_repository import LevelRepository
from app.modules.levels.domain.repositories.level_session_repository import LevelSessionRepository
from app.modules.levels.domain.services.level_access import LevelAccessService
from app.modules.progress.application.use_cases.complete_level import CompleteLevelUseCase
from app.modules.progress.domain.repositories.progress_repository import ProgressRepository
from app.modules.submissions.domain.entities.submission import Submission, SubmissionStatus
from app.modules.submissions.domain.repositories.submission_repository import SubmissionRepository
from app.modules.submissions.domain.services.verification_engine import VerificationEngine
from app.modules.users.domain.repositories.user_repository import UserRepository
from app.shared.events.event_bus import DomainEvent, EventPublisher

logger = logging.getLogger(__name__)


class LevelNotStartedError(ConflictError):
    code = "LEVEL_NOT_STARTED"


class InvalidSubmissionError(ForbiddenError):
    code = "INVALID_SUBMISSION"


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

    async def execute(self, user_id: str, level_id: str, payload: dict) -> LevelSubmitResult:
        level = await self._levels.get_by_id(level_id)
        if level is None:
            raise LevelNotFoundError("Level not found")

        latest_session = await self._sessions.get_latest(user_id, level_id)
        state, _ = await self._access.state_for(user_id, level, latest_session)
        if state == LevelState.LOCKED:
            raise InvalidSubmissionError("Level is locked")

        session = await self._sessions.get_active(user_id, level_id)
        if session is None:
            raise LevelNotStartedError("Start the level before submitting proof")

        attempt_number = await self._submissions.count_for_user_level(user_id, level_id) + 1
        submission = await self._submissions.create(
            Submission(
                id=str(uuid4()),
                user_id=user_id,
                level_id=level_id,
                session_id=session.id,
                attempt_number=attempt_number,
                payload=payload,
                status=SubmissionStatus.PENDING,
                verification_message="Verification pending",
            )
        )

        verification_result = self._verification.verify(level.verification_config, payload)
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
        progress = None
        certification = None
        unlocked_next_level_id = None

        if verification_result.verified:
            session.state = LevelState.COMPLETED
            session.completed_at = now
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
