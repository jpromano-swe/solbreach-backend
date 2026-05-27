from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath

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
    SandboxRuntime,
    SandboxTerminalEvent,
)
from app.modules.users.domain.entities.user import User
from app.modules.users.domain.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


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
        return _session_payload(session, manifest, files, terminal_events=terminal)

    async def get_session(self, user: User, session_id: str) -> dict:
        session = await self._owned_session(user.id, session_id)
        manifest = _manifest_for(session.lab_id)
        files = await self._repository.list_files(session.id)
        terminal = await self._repository.list_terminal_events(session.id, None)
        latest_run = await self._repository.latest_test_run(session.id)
        return _session_payload(
            session,
            manifest,
            files,
            terminal_events=terminal,
            latest_test_run=latest_run,
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

    async def submit_transaction(
        self, user: User, session_id: str, action_type: str, parameters: dict
    ) -> dict:
        session = await self._owned_active_session(user.id, session_id)
        result = await self._runtime.submit_transaction(session.id, action_type, parameters)
        transaction = await self._repository.create_transaction(
            session_id=session.id,
            transaction_ref=result.transaction_ref,
            instruction_type=result.instruction_type,
            execution_status=result.execution_status,
            logs=result.logs,
            submitted_at=datetime.now(UTC),
        )
        session.objective_progress = max(session.objective_progress, 3)
        await self._repository.update_session(session)
        return _transaction_payload(transaction, user_facing_evidence=result.user_facing_evidence)

    async def list_transactions(self, user: User, session_id: str) -> dict:
        session = await self._owned_session(user.id, session_id)
        transactions = await self._repository.list_transactions(session.id)
        return {
            "session_id": session.id,
            "transactions": [_transaction_payload(transaction) for transaction in transactions],
        }

    async def transaction_logs(
        self, user: User, session_id: str, transaction_ref: str
    ) -> dict:
        session = await self._owned_session(user.id, session_id)
        transaction = await self._repository.get_transaction(session.id, transaction_ref)
        if transaction is None:
            raise NotFoundError("Research lab transaction not found")
        logs = await self._runtime.get_transaction_logs(session.id, transaction_ref)
        return {"session_id": session.id, "transaction_ref": transaction_ref, "logs": logs}

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
            session.status = ResearchLabSessionStatus.PASSED.value
            session.objective_progress = len(manifest.objectives)
            await self._repository.update_session(session)
        return {
            "session_id": session.id,
            "objective_ref": result.objective_ref,
            "passed": result.passed,
            "phase": _phase_for(session),
            "exploitVerified": result.passed,
            "reportUnlocked": result.passed,
            "userFacingEvidence": result.user_facing_evidence,
        }

    async def get_report(self, user: User, session_id: str) -> dict:
        session = await self._owned_session(user.id, session_id)
        if session.status != ResearchLabSessionStatus.PASSED.value:
            return {
                "session_id": session.id,
                "status": ResearchLabReportStatus.LOCKED.value,
                "fields": None,
                "feedback": "Verify exploit impact in the sandbox to unlock the research report.",
            }

        report = await self._repository.get_report(session.id)
        if report is None:
            return _report_payload(
                session_id=session.id,
                status=ResearchLabReportStatus.DRAFT.value,
                fields=_empty_report_fields(),
                feedback=None,
                include_allowed_values=True,
            )
        return _stored_report_payload(report, include_allowed_values=True)

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
        return _stored_report_payload(model, include_updated_at=True)

    async def submit_report(self, user: User, session_id: str) -> dict:
        session = await self._owned_report_session(user.id, session_id)
        manifest = _manifest_for(session.lab_id)
        report = await self._repository.get_report(session.id)
        fields = report.fields_json if report is not None else _empty_report_fields()
        validation = _validate_report(session.lab_id, fields)
        now = datetime.now(UTC)

        if validation["accepted"]:
            xp_awarded = await self._award_xp_once(user, session, manifest, now)
            session.completed_at = now
            session.xp_awarded = max(session.xp_awarded, xp_awarded)
            await self._repository.update_session(session)
            model = await self._repository.upsert_report(
                session_id=session.id,
                user_id=user.id,
                lab_id=session.lab_id,
                status=ResearchLabReportStatus.ACCEPTED.value,
                fields=_normalize_report_fields(fields),
                feedback=(
                    "Report accepted. Vulnerability, impact, and remediation are correctly "
                    "identified."
                ),
                validation_result=validation,
                submitted_at=now,
                accepted_at=now,
            )
            return {
                "session_id": session.id,
                "status": model.status,
                "lab_completed": True,
                "xp_awarded": xp_awarded,
                "feedback": model.feedback,
            }

        model = await self._repository.upsert_report(
            session_id=session.id,
            user_id=user.id,
            lab_id=session.lab_id,
            status=ResearchLabReportStatus.RETRY.value,
            fields=_normalize_report_fields(fields),
            feedback="Root cause or remediation does not match this lab's vulnerability model.",
            validation_result=validation,
            submitted_at=now,
            accepted_at=None,
        )
        return {
            "session_id": session.id,
            "status": model.status,
            "lab_completed": False,
            "xp_awarded": 0,
            "feedback": model.feedback,
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
        session.completed_at = None
        await self._repository.append_terminal_events(
            session_id=session.id,
            test_run_id=None,
            events=[
                SandboxTerminalEvent("system", "Session reset. Environment restored.")
            ],
        )
        await self._repository.update_session(session)
        terminal = await self._repository.list_terminal_events(session.id, None)
        return _session_payload(session, manifest, files, terminal_events=terminal)

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
            ResearchLabSessionStatus.DESTROYED.value,
            ResearchLabSessionStatus.EXPIRED.value,
        }:
            raise ConflictError("Research lab session is not active")
        return session

    async def _owned_report_session(self, user_id: str, session_id: str) -> ResearchLabSessionModel:
        session = await self._owned_session(user_id, session_id)
        if session.status != ResearchLabSessionStatus.PASSED.value:
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
        if lab.id == lab_id or lab.slug == lab_id:
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
    latest_test_run: ResearchLabTestRunModel | None = None,
) -> dict:
    phase = _phase_for(session)
    report_unlocked = session.status == ResearchLabSessionStatus.PASSED.value
    return {
        "session_id": session.id,
        "sessionId": session.id,
        "lab_id": session.lab_id,
        "labId": session.lab_id,
        "lab_slug": session.lab_slug,
        "labVersion": manifest.version,
        "status": session.status,
        "sandboxStatus": _sandbox_status_for(session),
        "stage": _stage_for(session),
        "phase": phase,
        "exploitVerified": report_unlocked,
        "reportUnlocked": report_unlocked,
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


def _stage_for(session: ResearchLabSessionModel) -> str:
    phase = _phase_for(session)
    return phase.lower()


def _phase_for(session: ResearchLabSessionModel) -> str:
    if session.completed_at is not None:
        return "COMPLETED"
    if session.status == ResearchLabSessionStatus.PASSED.value:
        return "REPORT"
    if session.status == ResearchLabSessionStatus.RUNNING_TESTS.value:
        return "PROVE_IMPACT"
    if session.objective_progress >= 3:
        return "PROVE_IMPACT"
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
    if phase in {"REPORT", "COMPLETED"}:
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


def _transaction_payload(
    transaction: ResearchLabTransactionModel, *, user_facing_evidence: list[str] | None = None
) -> dict:
    return {
        "transaction_ref": transaction.transaction_ref,
        "transactionRef": transaction.transaction_ref,
        "instruction_type": transaction.instruction_type,
        "instructionType": transaction.instruction_type,
        "execution_status": transaction.execution_status,
        "executionStatus": transaction.execution_status,
        "logs": transaction.logs_json,
        "submitted_at": transaction.submitted_at.isoformat(),
        "submittedAt": transaction.submitted_at.isoformat(),
        "userFacingEvidence": user_facing_evidence or [],
    }


def _empty_report_fields() -> dict[str, str | None]:
    return {
        "vulnerability_category": None,
        "affected_area": None,
        "attacker_controlled_input": None,
        "root_cause": "",
        "impact": "",
        "proof": "",
        "recommended_fix": "",
        "severity": None,
    }


def _allowed_report_values() -> dict[str, list[str]]:
    return {
        "vulnerability_category": ["missing_validation", "arithmetic_safety"],
        "affected_area": ["deposit_instruction", "vault_health_calculation"],
        "attacker_controlled_input": [
            "collateral_token_account",
            "collateral_mint",
            "vault_account",
        ],
        "severity": ["low", "medium", "high"],
    }


def _normalize_report_fields(fields: dict) -> dict[str, str | None]:
    defaults = _empty_report_fields()
    normalized = {}
    for key, default in defaults.items():
        value = fields.get(key, default)
        normalized[key] = value.strip() if isinstance(value, str) else value
    return normalized


def _report_payload(
    *,
    session_id: str,
    status: str,
    fields: dict[str, str | None],
    feedback: str | None,
    include_allowed_values: bool = False,
    updated_at: str | None = None,
) -> dict:
    payload = {
        "session_id": session_id,
        "status": status,
        "fields": fields,
        "feedback": feedback,
    }
    if include_allowed_values:
        payload["allowed_values"] = _allowed_report_values()
    if updated_at is not None:
        payload["updated_at"] = updated_at
    return payload


def _stored_report_payload(
    report: ResearchLabReportModel,
    *,
    include_allowed_values: bool = False,
    include_updated_at: bool = False,
) -> dict:
    return _report_payload(
        session_id=report.session_id,
        status=report.status,
        fields=_normalize_report_fields(report.fields_json),
        feedback=report.feedback,
        include_allowed_values=include_allowed_values,
        updated_at=report.updated_at.isoformat() if include_updated_at else None,
    )


def _validate_report(lab_id: str, fields: dict) -> dict:
    normalized = _normalize_report_fields(fields)
    if lab_id in {"rl-001", "treasury-mirage", "rl-000", "mint-gate"}:
        return _validate_against_model(
            normalized,
            expected_category="missing_validation",
            expected_area="deposit_instruction",
            accepted_severities={"medium"},
            root_cause_groups=[["missing", "validation"], ["mint"], ["token", "account"]],
            impact_groups=[["counterfeit", "fake"], ["credit", "withdraw", "treasury"]],
            fix_groups=[["check", "validate", "require"], ["mint"], ["accepted", "official"]],
        )
    if lab_id in {"rl-007", "vault-mirage"}:
        return _validate_against_model(
            normalized,
            expected_category="arithmetic_safety",
            expected_area="vault_health_calculation",
            accepted_severities={"medium", "high"},
            root_cause_groups=[
                ["unchecked", "overflow", "checked"],
                ["multiplication", "division", "scaling", "scale"],
            ],
            impact_groups=[
                ["distort", "distorted", "incorrect", "inflated"],
                ["collateral", "health"],
            ],
            fix_groups=[["checked", "safe"], ["arithmetic", "math"], ["comparison", "health"]],
        )
    return {
        "accepted": False,
        "failed_checks": ["unsupported_lab"],
    }


def _validate_against_model(
    fields: dict[str, str | None],
    *,
    expected_category: str,
    expected_area: str,
    accepted_severities: set[str],
    root_cause_groups: list[list[str]],
    impact_groups: list[list[str]],
    fix_groups: list[list[str]],
) -> dict:
    failed = []
    if fields["vulnerability_category"] != expected_category:
        failed.append("vulnerability_category")
    if fields["affected_area"] != expected_area:
        failed.append("affected_area")
    if fields["severity"] not in accepted_severities:
        failed.append("severity")
    if not _has_concepts(str(fields["root_cause"] or ""), root_cause_groups):
        failed.append("root_cause")
    if not _has_concepts(str(fields["impact"] or ""), impact_groups):
        failed.append("impact")
    if not _has_concepts(str(fields["recommended_fix"] or ""), fix_groups):
        failed.append("recommended_fix")
    if len(str(fields["proof"] or "").strip()) < 20:
        failed.append("proof")
    return {
        "accepted": not failed,
        "failed_checks": failed,
    }


def _has_concepts(value: str, concept_groups: list[list[str]]) -> bool:
    normalized = value.lower()
    return all(any(term in normalized for term in group) for group in concept_groups)
