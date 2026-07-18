from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from uuid import uuid4

from app.core.config.settings import Settings
from app.core.exceptions.domain import ConflictError, ForbiddenError, NotFoundError
from app.modules.labs.domain.research_lab import (
    RESEARCH_LABS,
    ResearchLabManifest,
    ResearchLabReportStatus,
    ResearchLabSessionStatus,
    ResearchLabTestRunStatus,
)
from app.modules.labs.infrastructure.database.models import (
    ResearchLabFileModel,
    ResearchLabReportModel,
    ResearchLabSessionModel,
    ResearchLabTerminalEventModel,
    ResearchLabTestRunModel,
    ResearchLabTransactionModel,
)
from app.modules.labs.infrastructure.repositories.sqlalchemy_research_lab_repository import (
    SQLAlchemyResearchLabRepository,
)
from app.modules.sandbox.domain.runtime import (
    SandboxAccountSnapshot,
    SandboxAccountSummary,
    SandboxExplorerSnapshot,
    SandboxRuntime,
    SandboxTerminalEvent,
)
from app.modules.users.domain.entities.user import User
from app.modules.users.domain.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


RL1_FINDING_REVIEW_QUESTIONS: dict[str, dict[str, object]] = {
    "q1_vulnerability_category": {
        "correct": "account_substitution",
        "critical": True,
    },
    "q2_invalid_inputs": {
        "correct": "candidate_collateral_and_external_vault",
        "critical": False,
    },
    "q3_credit_origin": {
        "correct": "invalid_account_relationship_created_credit",
        "critical": False,
    },
    "q4_exploit_sequence": {
        "correct": "invalid_deposit_then_treasury_withdrawal",
        "critical": True,
    },
    "q5_treasury_impact": {
        "correct": "real_protocol_value_left_treasury",
        "critical": False,
    },
    "q6_impact_proven": {
        "correct": "only_after_invalid_credit_enables_real_withdrawal",
        "critical": True,
    },
    "q7_evidence_source": {
        "correct": "transaction_and_account_evidence",
        "critical": False,
    },
    "q8_recommended_fix": {
        "correct": "bind_accounts_to_approved_config",
        "critical": True,
    },
}

RL1_REPORT_OPTIONS: dict[str, list[dict[str, str]]] = {
    "titleOptionId": [
        {
            "id": "missing_constraints_counterfeit_credit",
            "label": "Missing constraints allow counterfeit collateral credit",
        }
    ],
    "severityOptionId": [
        {"id": "high_treasury_loss", "label": "High — treasury value can be drained"}
    ],
    "likelihoodOptionId": [
        {
            "id": "medium_high_attacker_supplied_accounts",
            "label": "Medium-High — attacker controls supplied account set",
        }
    ],
    "categoryOptionId": [{"id": "account_substitution", "label": "Account substitution"}],
    "rootCauseOptionId": [{"id": "missing_account_binding", "label": "Missing account binding"}],
    "proofOfImpactOptionId": [
        {
            "id": "counterfeit_credit_withdraws_treasury",
            "label": "Counterfeit credit enabled real treasury withdrawal",
        }
    ],
    "recommendedMitigationOptionId": [
        {
            "id": "bind_accounts_to_approved_config",
            "label": "Bind supplied accounts to approved protocol configuration",
        }
    ],
}


class ResearchLabService:
    def __init__(
        self,
        repository: SQLAlchemyResearchLabRepository,
        users: UserRepository,
        runtime: SandboxRuntime,
        settings: Settings,
    ) -> None:
        self._repository = repository
        self._users = users
        self._runtime = runtime
        self._settings = settings

    async def list_labs(self) -> list[dict]:
        return [lab.learner_safe() for lab in RESEARCH_LABS if lab.status == "active"]

    async def get_lab(self, lab_id: str) -> dict:
        return _manifest_for(lab_id).learner_safe(include_details=True)

    async def create_session(self, user: User, lab_id: str) -> dict:
        manifest = _manifest_for(lab_id)
        now = datetime.now(UTC)
        expires_at = now + timedelta(hours=self._settings.research_lab_session_ttl_hours)
        session = await self._repository.create_session(
            user_id=user.id,
            lab_id=manifest.id,
            lab_slug=manifest.slug,
            template_ref=manifest.template_ref,
            runtime_type="local_process",
            runtime_instance_ref="",
            status=ResearchLabSessionStatus.PROVISIONING.value,
            objective_progress=1,
            started_at=now,
            expires_at=expires_at,
        )
        runtime_ref = await self._runtime.create_session(session.id, manifest.template_ref)
        session.runtime_instance_ref = runtime_ref
        session.status = ResearchLabSessionStatus.ACTIVE.value

        files = []
        for path in manifest.allowed_files:
            content = await self._runtime.read_file(session.id, path)
            file_model = await self._repository.create_file(
                session_id=session.id,
                path=path,
                content=content,
                writable=False,
            )
            files.append(file_model)

        terminal = await self._repository.append_terminal_events(
            session_id=session.id,
            test_run_id=None,
            events=[
                SandboxTerminalEvent(
                    "system",
                    (
                        "Sandbox ready. Inspect code/accounts, submit an exploit action, "
                        "then verify impact."
                    ),
                )
            ],
        )
        await self._repository.update_session(session)
        logger.info(
            "research_lab_session_started",
            extra={"user_id": user.id, "session_id": session.id, "lab_id": manifest.id},
        )
        return _session_payload(
            session,
            manifest,
            files,
            terminal_events=terminal,
            transaction_count=0,
            report_status=ResearchLabReportStatus.LOCKED.value,
            protocol_state=_initial_protocol_state(manifest),
        )

    async def get_session(self, user: User, session_id: str) -> dict:
        session = await self._owned_session(user.id, session_id)
        manifest = _manifest_for(session.lab_id)
        files = await self._repository.list_files(session.id)
        terminal = await self._repository.list_terminal_events(session.id, None)
        latest_run = await self._repository.latest_test_run(session.id)
        transactions = await self._repository.list_transactions(session.id)
        report = await self._repository.get_report(session.id)
        latest_protocol_state = (
            transactions[-1].protocol_state_json
            if transactions
            else _initial_protocol_state(manifest)
        )
        return _session_payload(
            session,
            manifest,
            files,
            terminal_events=terminal,
            latest_test_run=latest_run,
            transaction_count=len(transactions),
            report_status=report.status if report is not None else _report_status_for(session),
            protocol_state=latest_protocol_state,
        )

    async def patch_files(self, user: User, session_id: str, files: list[dict[str, str]]) -> dict:
        session = await self._owned_active_session(user.id, session_id)
        manifest = _manifest_for(session.lab_id)

        updated: list[ResearchLabFileModel] = []
        for item in files:
            path = item["path"]
            content = item["content"]
            _validate_patch(
                path,
                content,
                manifest,
                self._settings.research_lab_max_file_size_bytes,
            )
            file_model = await self._repository.get_file(session.id, path)
            if file_model is None or not file_model.writable:
                raise ForbiddenError("File is not writable for this lab")
            await self._runtime.patch_file(session.id, path, content)
            updated.append(await self._repository.update_file(file_model, content))

        session.status = ResearchLabSessionStatus.DIRTY.value
        session.objective_progress = max(session.objective_progress, 3)
        await self._repository.update_session(session)
        await self._repository.append_terminal_events(
            session_id=session.id,
            test_run_id=None,
            events=[SandboxTerminalEvent("system", "Files saved. Sandbox is ready for tests.")],
        )
        return {
            "session_id": session.id,
            "status": session.status,
            "files": [_file_payload(file) for file in updated],
        }

    async def run_tests(self, user: User, session_id: str) -> dict:
        session = await self._owned_active_session(user.id, session_id)
        if session.status == ResearchLabSessionStatus.RUNNING_TESTS.value:
            raise ConflictError("A test run is already active for this session")

        manifest = _manifest_for(session.lab_id)
        if not manifest.test_command:
            raise ConflictError("This research lab uses exploit verification instead of tests")
        now = datetime.now(UTC)
        session.status = ResearchLabSessionStatus.RUNNING_TESTS.value
        await self._repository.update_session(session)
        test_run = await self._repository.create_test_run(
            session_id=session.id,
            status=ResearchLabTestRunStatus.RUNNING.value,
            command=manifest.test_command,
            started_at=now,
        )
        logger.info(
            "research_lab_tests_started",
            extra={"user_id": user.id, "session_id": session.id, "lab_id": manifest.id},
        )
        result = await self._runtime.run_tests(
            session.id,
            manifest.test_command,
            self._settings.research_lab_test_timeout_seconds,
        )
        await self._repository.append_terminal_events(
            session_id=session.id,
            test_run_id=test_run.id,
            events=result.terminal_events,
        )

        finished_at = datetime.now(UTC)
        status = _test_status(result.status)
        await self._repository.finish_test_run(
            test_run, status=status.value, results=result.results, finished_at=finished_at
        )

        xp_awarded = 0
        if status == ResearchLabTestRunStatus.PASSED:
            session.status = ResearchLabSessionStatus.PASSED.value
            session.objective_progress = len(manifest.objectives)
        else:
            session.status = (
                ResearchLabSessionStatus.ERROR.value
                if status == ResearchLabTestRunStatus.ERROR
                else ResearchLabSessionStatus.FAILED.value
            )
            session.objective_progress = max(session.objective_progress, 3)

        session.xp_awarded = max(session.xp_awarded, xp_awarded)
        await self._repository.update_session(session)
        logger.info(
            "research_lab_tests_finished",
            extra={
                "user_id": user.id,
                "session_id": session.id,
                "lab_id": manifest.id,
                "status": status.value,
                "xp_awarded": xp_awarded,
            },
        )
        return {
            "test_run_id": test_run.id,
            "status": status.value,
            "results": test_run.results_json,
            "objective_progress": session.objective_progress,
            "session_status": session.status,
            "lab_completed": False,
            "report_status": (
                ResearchLabReportStatus.DRAFT.value
                if status == ResearchLabTestRunStatus.PASSED
                else ResearchLabReportStatus.LOCKED.value
            ),
            "xp_awarded": xp_awarded,
        }

    async def list_accounts(self, user: User, session_id: str) -> dict:
        session = await self._owned_session(user.id, session_id)
        accounts = await self._runtime.get_visible_accounts(session.id)
        return {
            "session_id": session.id,
            "accounts": [_account_summary_payload(account) for account in accounts],
        }

    async def get_account(self, user: User, session_id: str, account_ref: str) -> dict:
        session = await self._owned_session(user.id, session_id)
        account = await self._runtime.get_account_state(session.id, account_ref)
        return {"session_id": session.id, "account": _account_snapshot_payload(account)}

    async def get_explorer(self, user: User, session_id: str) -> dict:
        session = await self._owned_session(user.id, session_id)
        snapshot = await self._runtime.get_explorer_snapshot(session.id)
        return _explorer_payload(snapshot)

    async def submit_transaction(
        self, user: User, session_id: str, action_type: str, parameters: dict
    ) -> dict:
        session = await self._owned_active_session(user.id, session_id)
        result = await self._runtime.submit_transaction(session.id, action_type, parameters)
        idempotency_key = parameters.get("idempotency_key", str(uuid4()))
        evidence_refs = [f"transaction:{result.transaction_ref}"]
        transaction = await self._repository.create_transaction(
            session_id=session.id,
            transaction_ref=result.transaction_ref,
            instruction_type=result.instruction_type,
            parameters=parameters,
            execution_status=result.execution_status,
            logs=result.logs,
            account_deltas=result.account_deltas,
            evidence_refs=evidence_refs,
            protocol_state=result.protocol_state,
            user_facing_evidence=result.user_facing_evidence,
            submitted_at=datetime.now(UTC),
            idempotency_key=idempotency_key,
        )
        session.objective_progress = max(session.objective_progress, 2)
        await self._repository.update_session(session)
        return _transaction_payload(
            transaction,
            protocol_state=result.protocol_state,
            user_facing_evidence=result.user_facing_evidence,
        )

    async def list_transactions(self, user: User, session_id: str) -> dict:
        session = await self._owned_session(user.id, session_id)
        transactions = await self._repository.list_transactions(session.id)
        return {
            "session_id": session.id,
            "transactions": [_transaction_payload(transaction) for transaction in transactions],
        }

    async def transaction_logs(self, user: User, session_id: str, transaction_ref: str) -> dict:
        session = await self._owned_session(user.id, session_id)
        transaction = await self._repository.get_transaction(session.id, transaction_ref)
        if transaction is None:
            raise NotFoundError("Research lab transaction not found")
        return {
            "session_id": session.id,
            "transaction_ref": transaction_ref,
            "logs": transaction.logs_json,
        }

    async def verify_objective(
        self, user: User, session_id: str, objective_ref: str | None
    ) -> dict:
        session = await self._owned_active_session(user.id, session_id)
        manifest = _manifest_for(session.lab_id)
        result = await self._runtime.verify_objective(
            session.id, objective_ref or manifest.objective_ref
        )
        await self._repository.create_exploit_verification(
            session_id=session.id,
            objective_ref=result.objective_ref,
            passed=result.passed,
            evidence=result.evidence,
            verified_at=datetime.now(UTC),
        )
        if result.passed:
            session.status = ResearchLabSessionStatus.VERIFIED.value
            session.impact_verified = True
            session.verified_evidence_refs_json = result.verified_evidence_refs
            session.objective_progress = len(manifest.objectives)
        else:
            session.objective_progress = max(session.objective_progress, 3)
        await self._repository.update_session(session)
        logger.info(
            "research_lab_objective_verified"
            if result.passed
            else "research_lab_objective_rejected",
            extra={
                "user_id": user.id,
                "session_id": session.id,
                "lab_id": manifest.id,
                "objective_ref": result.objective_ref,
                "passed": result.passed,
                "failure_reason": result.failure_reason,
                "verified_evidence_refs": session.verified_evidence_refs_json,
            },
        )
        return {
            "session_id": session.id,
            "sessionId": session.id,
            "objective_ref": result.objective_ref,
            "objectiveRef": result.objective_ref,
            "passed": result.passed,
            "impactVerified": session.impact_verified,
            "verifiedEvidenceRefs": session.verified_evidence_refs_json,
            "reportUnlocked": session.impact_verified,
            "certificateUnlockable": _certificate_unlockable(session),
            "phase": _phase_for(
                session, transaction_count=await self._repository.count_transactions(session.id)
            ),
            "evidence": result.evidence,
            "failureReason": result.failure_reason,
            "userFacingEvidence": result.user_facing_evidence,
        }

    async def get_report(self, user: User, session_id: str) -> dict:
        session = await self._owned_session(user.id, session_id)
        if not session.impact_verified:
            return {
                "session_id": session.id,
                "status": ResearchLabReportStatus.LOCKED.value,
                "impactVerified": False,
                "reportUnlocked": False,
                "fields": None,
                "feedback": "Verify exploit impact in the sandbox to unlock the audit report.",
                "verifiedEvidenceRefs": [],
                "certificateUnlockable": False,
            }

        report = await self._repository.get_report(session.id)
        if report is None:
            return _report_payload(
                session_id=session.id,
                session_id_alias=session.id,
                status=ResearchLabReportStatus.DRAFT.value,
                fields=_empty_report_fields(),
                feedback=None,
                impact_verified=session.impact_verified,
                include_allowed_values=True,
                verified_evidence_refs=session.verified_evidence_refs_json,
                certificate_unlockable=_certificate_unlockable(session),
            )
        return _stored_report_payload(
            report,
            impact_verified=session.impact_verified,
            include_allowed_values=True,
            verified_evidence_refs=session.verified_evidence_refs_json,
            certificate_unlockable=_certificate_unlockable(session),
        )

    async def save_report_draft(
        self, user: User, session_id: str, fields: dict[str, str | None]
    ) -> dict:
        session = await self._owned_report_session(user.id, session_id)
        existing = await self._repository.get_report(session.id)
        if existing is not None and existing.status == ResearchLabReportStatus.ACCEPTED.value:
            raise ConflictError("Research lab report is already accepted")

        model = await self._repository.upsert_report(
            session_id=session.id,
            user_id=user.id,
            lab_id=session.lab_id,
            status=ResearchLabReportStatus.DRAFT.value,
            fields=_normalize_report_fields(fields),
            feedback=None,
            validation_result=None,
            submitted_at=None,
            accepted_at=None,
        )
        logger.info(
            "research_lab_report_saved",
            extra={
                "user_id": user.id,
                "session_id": session.id,
                "lab_id": session.lab_id,
                "status": model.status,
                "has_verified_refs": bool(model.fields_json.get("verifiedEvidenceRefs")),
            },
        )
        return _stored_report_payload(
            model,
            impact_verified=session.impact_verified,
            include_updated_at=True,
            include_allowed_values=True,
            verified_evidence_refs=session.verified_evidence_refs_json,
            certificate_unlockable=_certificate_unlockable(session),
        )

    async def submit_report(self, user: User, session_id: str) -> dict:
        session = await self._owned_report_session(user.id, session_id)
        if not session.finding_review_passed:
            raise ConflictError("Pass the finding review before submitting the audit report")
        manifest = _manifest_for(session.lab_id)
        report = await self._repository.get_report(session.id)
        fields = report.fields_json if report is not None else _empty_report_fields()
        validation = _validate_report(session.lab_id, fields)
        evidence_refs = list(fields.get("verifiedEvidenceRefs") or [])
        if not evidence_refs:
            validation["accepted"] = False
            validation["failed_checks"] = list(validation["failed_checks"]) + [
                "verifiedEvidenceRefs"
            ]
        elif not set(evidence_refs).issubset(set(session.verified_evidence_refs_json)):
            validation["accepted"] = False
            validation["failed_checks"] = list(validation["failed_checks"]) + [
                "verifiedEvidenceRefs"
            ]
        now = datetime.now(UTC)

        if validation["accepted"]:
            xp_awarded = await self._award_xp_once(user, session, manifest, now)
            session.status = ResearchLabSessionStatus.COMPLETED.value
            session.completed_at = now
            session.xp_awarded = max(session.xp_awarded, xp_awarded)
            session.audit_report_builder_passed = True
            await self._repository.update_session(session)
            model = await self._repository.upsert_report(
                session_id=session.id,
                user_id=user.id,
                lab_id=session.lab_id,
                status=ResearchLabReportStatus.ACCEPTED.value,
                fields=_normalize_report_fields(fields),
                feedback=(
                    "Audit report accepted. Evidence, severity, root cause, and mitigation "
                    "align with the verified account substitution impact."
                ),
                validation_result=validation,
                submitted_at=now,
                accepted_at=now,
            )
            logger.info(
                "research_lab_report_accepted",
                extra={
                    "user_id": user.id,
                    "session_id": session.id,
                    "lab_id": session.lab_id,
                    "xp_awarded": xp_awarded,
                    "verified_evidence_refs": session.verified_evidence_refs_json,
                },
            )
            payload = _stored_report_payload(
                model,
                impact_verified=session.impact_verified,
                include_allowed_values=True,
                include_updated_at=True,
                verified_evidence_refs=session.verified_evidence_refs_json,
                certificate_unlockable=_certificate_unlockable(session),
            )
            payload.update(
                {
                    "lab_completed": True,
                    "labCompleted": True,
                    "xp_awarded": xp_awarded,
                    "xpAwarded": xp_awarded,
                }
            )
            return payload

        session.audit_report_builder_passed = False
        await self._repository.update_session(session)
        model = await self._repository.upsert_report(
            session_id=session.id,
            user_id=user.id,
            lab_id=session.lab_id,
            status=ResearchLabReportStatus.RETRY.value,
            fields=_normalize_report_fields(fields),
            feedback="Report option IDs do not match the verified RL1 vulnerability model.",
            validation_result=validation,
            submitted_at=now,
            accepted_at=None,
        )
        logger.warning(
            "research_lab_report_rejected",
            extra={
                "user_id": user.id,
                "session_id": session.id,
                "lab_id": session.lab_id,
                "failed_checks": validation["failed_checks"],
            },
        )
        payload = _stored_report_payload(
            model,
            impact_verified=session.impact_verified,
            include_allowed_values=True,
            include_updated_at=True,
            verified_evidence_refs=session.verified_evidence_refs_json,
            certificate_unlockable=_certificate_unlockable(session),
        )
        payload.update(
            {
                "lab_completed": False,
                "labCompleted": False,
                "xp_awarded": 0,
                "xpAwarded": 0,
            }
        )
        return payload

    async def get_finding_review(self, user: User, session_id: str) -> dict:
        session = await self._owned_session(user.id, session_id)
        if not session.impact_verified:
            return {
                "session_id": session.id,
                "status": "locked",
                "impactVerified": False,
                "reportUnlocked": False,
                "findingReviewPassed": False,
                "findingReviewAttempts": session.finding_review_attempts,
                "failedQuestionIds": [],
                "criticalQuestionsPassed": False,
                "certificateUnlockable": False,
                "feedback": "Verify exploit impact to unlock the finding review.",
            }
        return {
            "session_id": session.id,
            "status": (
                "passed"
                if session.finding_review_passed
                else "retry"
                if session.finding_review_attempts > 0
                else "draft"
            ),
            "impactVerified": session.impact_verified,
            "reportUnlocked": session.impact_verified,
            "findingReviewPassed": session.finding_review_passed,
            "findingReviewAttempts": session.finding_review_attempts,
            "failedQuestionIds": session.failed_question_ids_json,
            "criticalQuestionsPassed": session.critical_questions_passed,
            "score": session.finding_review_score,
            "feedback": session.finding_review_feedback,
            "certificateUnlockable": _certificate_unlockable(session),
            "questions": [
                {
                    "id": question_id,
                    "critical": bool(config["critical"]),
                }
                for question_id, config in RL1_FINDING_REVIEW_QUESTIONS.items()
            ],
        }

    async def submit_finding_review(
        self, user: User, session_id: str, answers: dict[str, str]
    ) -> dict:
        session = await self._owned_session(user.id, session_id)
        if not session.impact_verified:
            raise ConflictError("Verify exploit impact before submitting the finding review")
        validation = _validate_finding_review(answers)
        session.finding_review_attempts += 1
        session.finding_review_answers_json = answers
        session.finding_review_score = validation["score"]
        session.failed_question_ids_json = validation["failed_question_ids"]
        session.critical_questions_passed = validation["critical_questions_passed"]
        session.finding_review_passed = validation["passed"]
        session.finding_review_feedback = validation["feedback"]
        await self._repository.update_session(session)
        return {
            "session_id": session.id,
            "status": "passed" if validation["passed"] else "retry",
            "findingReviewPassed": session.finding_review_passed,
            "findingReviewAttempts": session.finding_review_attempts,
            "failedQuestionIds": session.failed_question_ids_json,
            "criticalQuestionsPassed": session.critical_questions_passed,
            "score": session.finding_review_score,
            "feedback": session.finding_review_feedback,
            "reportUnlocked": session.impact_verified,
            "certificateUnlockable": _certificate_unlockable(session),
        }

    async def terminal_events(
        self, user: User, session_id: str, after_sequence: int | None
    ) -> dict:
        session = await self._owned_session(user.id, session_id)
        events = await self._repository.list_terminal_events(session.id, after_sequence)
        latest = events[-1].sequence if events else (after_sequence or 0)
        return {"events": [_terminal_payload(event) for event in events], "latest_sequence": latest}

    async def reset_session(self, user: User, session_id: str) -> dict:
        session = await self._owned_session(user.id, session_id)
        manifest = _manifest_for(session.lab_id)
        await self._runtime.reset_session(session.id, manifest.template_ref)
        await self._repository.clear_runtime_state(session.id)
        files = []
        for path in manifest.allowed_files:
            content = await self._runtime.read_file(session.id, path)
            files.append(
                await self._repository.create_file(
                    session_id=session.id,
                    path=path,
                    content=content,
                    writable=False,
                )
            )
        session.status = ResearchLabSessionStatus.ACTIVE.value
        session.objective_progress = 1
        session.impact_verified = False
        session.verified_evidence_refs_json = []
        session.finding_review_passed = False
        session.finding_review_attempts = 0
        session.finding_review_score = 0
        session.finding_review_answers_json = {}
        session.failed_question_ids_json = []
        session.critical_questions_passed = False
        session.finding_review_feedback = None
        session.audit_report_builder_passed = False
        session.completed_at = None
        await self._repository.append_terminal_events(
            session_id=session.id,
            test_run_id=None,
            events=[SandboxTerminalEvent("system", "Session reset. Environment restored.")],
        )
        await self._repository.update_session(session)
        terminal = await self._repository.list_terminal_events(session.id, None)
        return _session_payload(
            session,
            manifest,
            files,
            terminal_events=terminal,
            transaction_count=0,
            report_status=ResearchLabReportStatus.LOCKED.value,
            protocol_state=_initial_protocol_state(manifest),
        )

    async def _owned_session(self, user_id: str, session_id: str) -> ResearchLabSessionModel:
        session = await self._repository.get_session(session_id)
        if session is None:
            raise NotFoundError("Research lab session not found")
        if session.user_id != user_id:
            raise ForbiddenError("Research lab session belongs to another user")
        if session.destroyed_at is not None:
            raise ConflictError("Research lab session was destroyed")
        if _as_aware_utc(session.expires_at) <= datetime.now(UTC):
            session.status = ResearchLabSessionStatus.EXPIRED.value
            await self._repository.update_session(session)
            raise ConflictError("Research lab session expired")
        return session

    async def _owned_active_session(self, user_id: str, session_id: str) -> ResearchLabSessionModel:
        session = await self._owned_session(user_id, session_id)
        if session.status in {
            ResearchLabSessionStatus.PASSED.value,
            ResearchLabSessionStatus.VERIFIED.value,
            ResearchLabSessionStatus.COMPLETED.value,
            ResearchLabSessionStatus.DESTROYED.value,
            ResearchLabSessionStatus.EXPIRED.value,
        }:
            raise ConflictError("Research lab session is not active")
        return session

    async def _owned_report_session(self, user_id: str, session_id: str) -> ResearchLabSessionModel:
        session = await self._owned_session(user_id, session_id)
        if not session.impact_verified:
            raise ConflictError("Verify exploit impact to unlock the research report")
        return session

    async def _award_xp_once(
        self,
        user: User,
        session: ResearchLabSessionModel,
        manifest: ResearchLabManifest,
        completed_at: datetime,
    ) -> int:
        completion = await self._repository.get_completion(user_id=user.id, lab_id=manifest.id)
        if completion is not None:
            return 0
        await self._repository.create_completion(
            user_id=user.id,
            lab_id=manifest.id,
            lab_slug=manifest.slug,
            session_id=session.id,
            xp_awarded=manifest.xp_reward,
            completed_at=completed_at,
        )
        user.xp += manifest.xp_reward
        await self._users.update(user)
        return manifest.xp_reward


def _manifest_for(lab_id: str) -> ResearchLabManifest:
    for lab in RESEARCH_LABS:
        if lab.id == lab_id or lab.slug == lab_id or lab_id in lab.aliases:
            return lab
    raise NotFoundError("Research lab not found")


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _validate_patch(
    path: str, content: str, manifest: ResearchLabManifest, max_file_size: int
) -> None:
    parsed = PurePosixPath(path)
    if parsed.is_absolute() or ".." in parsed.parts:
        raise ConflictError("Invalid file path")
    if path not in manifest.allowed_files:
        raise ForbiddenError("File is not writable for this lab")
    if "\x00" in content:
        raise ConflictError("Binary file content is not accepted")
    if len(content.encode("utf-8")) > max_file_size:
        raise ConflictError("File content exceeds the maximum size")


def _test_status(status: str) -> ResearchLabTestRunStatus:
    if status == "passed":
        return ResearchLabTestRunStatus.PASSED
    if status == "timeout":
        return ResearchLabTestRunStatus.TIMEOUT
    if status == "failed":
        return ResearchLabTestRunStatus.FAILED
    return ResearchLabTestRunStatus.ERROR


def _session_payload(
    session: ResearchLabSessionModel,
    manifest: ResearchLabManifest,
    files: list[ResearchLabFileModel],
    *,
    terminal_events: list[ResearchLabTerminalEventModel],
    transaction_count: int,
    report_status: str,
    protocol_state: dict,
    latest_test_run: ResearchLabTestRunModel | None = None,
) -> dict:
    phase = _phase_for(session, transaction_count=transaction_count)
    report_unlocked = session.impact_verified
    return {
        "session_id": session.id,
        "sessionId": session.id,
        "lab_id": session.lab_id,
        "labId": session.lab_id,
        "lab_slug": session.lab_slug,
        "labSlug": session.lab_slug,
        "labVersion": manifest.version,
        "status": session.status,
        "sandboxStatus": _sandbox_status_for(session),
        "stage": phase.lower(),
        "phase": phase,
        "impactVerified": session.impact_verified,
        "verifiedEvidenceRefs": session.verified_evidence_refs_json,
        "reportUnlocked": report_unlocked,
        "reportStatus": report_status,
        "protocolState": protocol_state,
        "findingReviewPassed": session.finding_review_passed,
        "findingReviewAttempts": session.finding_review_attempts,
        "failedQuestionIds": session.failed_question_ids_json,
        "criticalQuestionsPassed": session.critical_questions_passed,
        "auditReportBuilderPassed": session.audit_report_builder_passed,
        "certificateUnlockable": _certificate_unlockable(session),
        "labCompleted": session.completed_at is not None,
        "visibleTabs": _visible_tabs_for(phase),
        "scenarioBriefing": manifest.scenario_briefing,
        "objective_progress": session.objective_progress,
        "expires_at": session.expires_at.isoformat(),
        "expiresAt": session.expires_at.isoformat(),
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        "completedAt": session.completed_at.isoformat() if session.completed_at else None,
        "xp_awarded": session.xp_awarded,
        "allowed_files": manifest.allowed_files,
        "entry_file": manifest.entry_file,
        "files": [_file_payload(file) for file in files],
        "terminal": [_terminal_payload(event) for event in terminal_events],
        "objectives": [
            {"label": label, "completed": index < session.objective_progress}
            for index, label in enumerate(manifest.objectives)
        ],
        "latest_test_run": _test_run_payload(latest_test_run) if latest_test_run else None,
    }


def _phase_for(session: ResearchLabSessionModel, *, transaction_count: int) -> str:
    if session.completed_at is not None:
        return "COMPLETED"
    if session.impact_verified:
        return "SUBMIT_FINDING"
    if transaction_count > 0 and session.objective_progress >= 3:
        return "EVIDENCE_REVIEW"
    if transaction_count > 0:
        return "EXECUTE_EXPLOIT"
    return "INSPECT"


def _sandbox_status_for(session: ResearchLabSessionModel) -> str:
    if session.status == ResearchLabSessionStatus.PROVISIONING.value:
        return "PROVISIONING"
    if session.status == ResearchLabSessionStatus.EXPIRED.value:
        return "EXPIRED"
    if session.status == ResearchLabSessionStatus.ERROR.value:
        return "ERROR"
    if session.status == ResearchLabSessionStatus.RUNNING_TESTS.value:
        return "RUNNING"
    return "READY"


def _visible_tabs_for(phase: str) -> list[str]:
    tabs = ["CODE", "ACCOUNTS", "EXPLOIT", "TRANSACTIONS_LOGS"]
    if phase in {"SUBMIT_FINDING", "COMPLETED"}:
        tabs.append("FINDING_REVIEW")
        tabs.append("REPORT")
    return tabs


def _file_payload(file: ResearchLabFileModel) -> dict:
    return {
        "path": file.path,
        "language": "rust" if file.path.endswith(".rs") else "text",
        "writable": file.writable,
        "version": file.version,
        "content": file.content,
    }


def _terminal_payload(event: ResearchLabTerminalEventModel) -> dict:
    return {"sequence": event.sequence, "stream": event.stream, "line": event.line}


def _test_run_payload(test_run: ResearchLabTestRunModel) -> dict:
    return {
        "test_run_id": test_run.id,
        "status": test_run.status,
        "results": test_run.results_json,
        "started_at": test_run.started_at.isoformat(),
        "finished_at": test_run.finished_at.isoformat() if test_run.finished_at else None,
    }


def _account_summary_payload(account: SandboxAccountSummary) -> dict:
    return {
        "ref": account.ref,
        "label": account.label,
        "owner": account.owner,
        "lamports": account.lamports,
        "data": account.data,
    }


def _account_snapshot_payload(account: SandboxAccountSnapshot) -> dict:
    return {
        "ref": account.ref,
        "label": account.label,
        "owner": account.owner,
        "lamports": account.lamports,
        "data": account.data,
    }


def _explorer_payload(snapshot: SandboxExplorerSnapshot) -> dict:
    return {
        "session_id": snapshot.session_id,
        "sessionId": snapshot.session_id,
        "enabled": snapshot.enabled,
        "reason": snapshot.reason,
        "network": snapshot.network,
        "program": snapshot.program,
        "accounts": snapshot.accounts,
        "rewardCandidates": snapshot.reward_candidates,
        "totalRewardsPaid": snapshot.total_rewards_paid,
    }


def _transaction_payload(
    transaction: ResearchLabTransactionModel,
    *,
    user_facing_evidence: list | None = None,
    protocol_state: dict | None = None,
) -> dict:
    effective_protocol_state = protocol_state or transaction.protocol_state_json or {}
    treasury_impact_observed = any(
        int(delta.get("lamportsDelta", 0) or 0) < 0 and delta.get("accountRef") == "treasury_vault"
        for delta in (transaction.account_deltas_json or [])
    )
    return {
        "transaction_ref": transaction.transaction_ref,
        "transactionRef": transaction.transaction_ref,
        "instruction_type": transaction.instruction_type,
        "instructionType": transaction.instruction_type,
        "execution_status": transaction.execution_status,
        "executionStatus": transaction.execution_status,
        "logs": transaction.logs_json,
        "account_deltas": transaction.account_deltas_json,
        "accountDeltas": transaction.account_deltas_json,
        "evidence_refs": transaction.evidence_refs_json,
        "evidenceRefs": transaction.evidence_refs_json,
        "protocolState": effective_protocol_state,
        "protocol_state": effective_protocol_state,
        "exploitProvenance": effective_protocol_state.get("depositPathType"),
        "creditedCollateral": effective_protocol_state.get("creditedCollateral"),
        "maxBorrow": effective_protocol_state.get("maxBorrow"),
        "availableBorrow": effective_protocol_state.get("availableBorrow"),
        "borrowedTotal": effective_protocol_state.get("borrowedTotal"),
        "treasuryImpactObserved": treasury_impact_observed,
        "submitted_at": transaction.submitted_at.isoformat(),
        "submittedAt": transaction.submitted_at.isoformat(),
        "userFacingEvidence": user_facing_evidence or transaction.user_facing_evidence_json or [],
    }


def _empty_report_fields() -> dict[str, str | None]:
    return {
        "titleOptionId": None,
        "severityOptionId": None,
        "likelihoodOptionId": None,
        "categoryOptionId": None,
        "rootCauseOptionId": None,
        "proofOfImpactOptionId": None,
        "recommendedMitigationOptionId": None,
        "verifiedEvidenceRefs": [],
        "optionalNotes": None,
    }


def _allowed_report_values() -> dict[str, list[dict[str, str]]]:
    return RL1_REPORT_OPTIONS.copy()


def _normalize_report_fields(fields: dict) -> dict[str, str | None]:
    defaults = _empty_report_fields()
    normalized = {}
    for key, default in defaults.items():
        value = fields.get(key, default)
        if isinstance(default, list):
            normalized[key] = [item for item in value or [] if isinstance(item, str)]
        else:
            normalized[key] = value.strip() if isinstance(value, str) else value
    return normalized


def _report_payload(
    *,
    session_id: str,
    session_id_alias: str | None = None,
    status: str,
    fields: dict[str, str | None],
    feedback: str | None,
    impact_verified: bool,
    include_allowed_values: bool = False,
    verified_evidence_refs: list[str] | None = None,
    certificate_unlockable: bool = False,
    updated_at: str | None = None,
) -> dict:
    payload = {
        "session_id": session_id,
        "sessionId": session_id_alias or session_id,
        "status": status,
        "impactVerified": impact_verified,
        "reportUnlocked": impact_verified,
        "fields": fields,
        "feedback": feedback,
        "verifiedEvidenceRefs": verified_evidence_refs or [],
        "certificateUnlockable": certificate_unlockable,
    }
    if include_allowed_values:
        payload["allowed_values"] = _allowed_report_values()
        payload["allowedValues"] = _allowed_report_values()
    if updated_at is not None:
        payload["updated_at"] = updated_at
        payload["updatedAt"] = updated_at
    return payload


def _stored_report_payload(
    report: ResearchLabReportModel,
    *,
    impact_verified: bool,
    include_allowed_values: bool = False,
    include_updated_at: bool = False,
    verified_evidence_refs: list[str] | None = None,
    certificate_unlockable: bool = False,
) -> dict:
    return _report_payload(
        session_id=report.session_id,
        session_id_alias=report.session_id,
        status=report.status,
        fields=_normalize_report_fields(report.fields_json),
        feedback=report.feedback,
        impact_verified=impact_verified,
        include_allowed_values=include_allowed_values,
        verified_evidence_refs=verified_evidence_refs,
        certificate_unlockable=certificate_unlockable,
        updated_at=report.updated_at.isoformat() if include_updated_at else None,
    )


def _validate_report(lab_id: str, fields: dict) -> dict:
    normalized = _normalize_report_fields(fields)
    expected = {
        "titleOptionId": "missing_constraints_counterfeit_credit",
        "severityOptionId": "high_treasury_loss",
        "likelihoodOptionId": "medium_high_attacker_supplied_accounts",
        "categoryOptionId": "account_substitution",
        "rootCauseOptionId": "missing_account_binding",
        "proofOfImpactOptionId": "counterfeit_credit_withdraws_treasury",
        "recommendedMitigationOptionId": "bind_accounts_to_approved_config",
    }
    failed = [
        key for key, expected_value in expected.items() if normalized.get(key) != expected_value
    ]
    if not normalized.get("verifiedEvidenceRefs"):
        failed.append("verifiedEvidenceRefs")
    return {"accepted": not failed, "failed_checks": failed}


def _initial_protocol_state(manifest: ResearchLabManifest | None = None) -> dict:
    if manifest is not None and manifest.id == "rl2-yield-hijack":
        return {
            "pool": {
                "advertisedApyBps": 250_000,
                "stakeVaultBalance": 50_000,
                "rewardVaultBalance": 500_000,
                "baselineRewardVaultBalance": 500_000,
            },
            "position": {
                "stakedAmount": 50_000,
                "baselineStakedAmount": 50_000,
                "pendingRewards": 12_500,
                "baselinePendingRewards": 12_500,
            },
            "attacker": {
                "stakeBalance": 100,
                "rewardBalance": 0,
                "baselineStakeBalance": 100,
                "baselineRewardBalance": 0,
            },
            "victim": {
                "stakeBalance": 0,
                "rewardBalance": 0,
                "baselineStakedAmount": 50_000,
                "baselinePendingRewards": 12_500,
            },
            "successfulStakes": [],
            "successfulClaims": [],
            "failedTransactions": [],
            "attackerStakedTotal": 0,
            "rewardsClaimedTotal": 0,
            "positionDerivationCollision": True,
        }
    return {
        "depositPathType": "none",
        "officialCollateral": 50_000,
        "counterfeitCollateral": 0,
        "creditedCollateral": 50_000,
        "effectiveCreditedCollateral": 50_000,
        "poolLiquidity": 100_000,
        "treasuryLamports": 100_000,
        "initialTreasuryLamports": 100_000,
        "rewardLamports": 0,
        "successfulDeposits": [],
        "successfulWithdrawals": [],
        "maxBorrow": 40_000,
        "availableBorrow": 40_000,
        "maxDrainAmount": 40_000,
        "borrowedTotal": 0,
        "borrowAllowed": True,
        "ltvBps": 8000,
        "hasOfficialDeposit": False,
        "hasExploitDeposit": False,
        "maxDrainSatisfied": False,
    }


def _validate_finding_review(answers: dict[str, str]) -> dict[str, object]:
    failed_question_ids: list[str] = []
    failed_critical_questions: list[str] = []
    total = len(RL1_FINDING_REVIEW_QUESTIONS)
    for question_id, config in RL1_FINDING_REVIEW_QUESTIONS.items():
        if answers.get(question_id) != config["correct"]:
            failed_question_ids.append(question_id)
            if bool(config["critical"]):
                failed_critical_questions.append(question_id)
    score = int(round(((total - len(failed_question_ids)) / total) * 100))
    critical_questions_passed = len(failed_critical_questions) == 0
    passed = score >= 80 and critical_questions_passed
    feedback = (
        "Finding review passed. Backend-confirmed exploit impact can now support the audit report."
        if passed
        else "Finding review failed. One or more critical exploit-understanding questions are incorrect."
    )
    return {
        "passed": passed,
        "score": score,
        "failed_question_ids": failed_question_ids,
        "critical_questions_passed": critical_questions_passed,
        "feedback": feedback,
    }


def _certificate_unlockable(session: ResearchLabSessionModel) -> bool:
    return bool(
        session.impact_verified
        and session.finding_review_passed
        and session.audit_report_builder_passed
        and session.verified_evidence_refs_json
    )


def _report_status_for(session: ResearchLabSessionModel) -> str:
    if session.audit_report_builder_passed:
        return ResearchLabReportStatus.ACCEPTED.value
    if session.impact_verified:
        return ResearchLabReportStatus.DRAFT.value
    return ResearchLabReportStatus.LOCKED.value
