from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.domain import ConflictError

from app.modules.labs.infrastructure.database.models import (
    ResearchLabCompletionModel,
    ResearchLabExploitVerificationModel,
    ResearchLabFileModel,
    ResearchLabReportModel,
    ResearchLabSessionModel,
    ResearchLabTerminalEventModel,
    ResearchLabTestRunModel,
    ResearchLabTransactionModel,
)
from app.modules.sandbox.domain.runtime import SandboxTerminalEvent, SandboxTestResult


class SQLAlchemyResearchLabRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_session(
        self,
        *,
        user_id: str,
        lab_id: str,
        lab_slug: str,
        template_ref: str,
        runtime_type: str,
        runtime_instance_ref: str,
        status: str,
        objective_progress: int,
        started_at: datetime,
        expires_at: datetime,
    ) -> ResearchLabSessionModel:
        model = ResearchLabSessionModel(
            id=str(uuid4()),
            user_id=user_id,
            lab_id=lab_id,
            lab_slug=lab_slug,
            template_ref=template_ref,
            runtime_type=runtime_type,
            runtime_instance_ref=runtime_instance_ref,
            status=status,
            objective_progress=objective_progress,
            started_at=started_at,
            expires_at=expires_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return model

    async def get_session(self, session_id: str) -> ResearchLabSessionModel | None:
        return await self._session.get(ResearchLabSessionModel, session_id)

    async def update_session(self, model: ResearchLabSessionModel) -> ResearchLabSessionModel:
        await self._session.flush()
        await self._session.refresh(model)
        return model

    async def create_file(
        self, *, session_id: str, path: str, content: str, writable: bool
    ) -> ResearchLabFileModel:
        model = ResearchLabFileModel(
            id=str(uuid4()),
            session_id=session_id,
            path=path,
            content=content,
            writable=writable,
            version=1,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return model

    async def list_files(self, session_id: str) -> list[ResearchLabFileModel]:
        result = await self._session.execute(
            select(ResearchLabFileModel)
            .where(ResearchLabFileModel.session_id == session_id)
            .order_by(ResearchLabFileModel.path)
        )
        return list(result.scalars().all())

    async def get_file(self, session_id: str, path: str) -> ResearchLabFileModel | None:
        result = await self._session.execute(
            select(ResearchLabFileModel).where(
                ResearchLabFileModel.session_id == session_id,
                ResearchLabFileModel.path == path,
            )
        )
        return result.scalar_one_or_none()

    async def update_file(self, model: ResearchLabFileModel, content: str) -> ResearchLabFileModel:
        model.content = content
        model.version += 1
        await self._session.flush()
        await self._session.refresh(model)
        return model

    async def create_test_run(
        self, *, session_id: str, status: str, command: str, started_at: datetime
    ) -> ResearchLabTestRunModel:
        model = ResearchLabTestRunModel(
            id=str(uuid4()),
            session_id=session_id,
            status=status,
            command=command,
            results_json=[],
            started_at=started_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return model

    async def finish_test_run(
        self,
        model: ResearchLabTestRunModel,
        *,
        status: str,
        results: list[SandboxTestResult],
        finished_at: datetime,
    ) -> ResearchLabTestRunModel:
        model.status = status
        model.results_json = [
            {
                "id": result.id,
                "label": result.label,
                "passed": result.passed,
                "details": result.details,
            }
            for result in results
        ]
        model.finished_at = finished_at
        await self._session.flush()
        await self._session.refresh(model)
        return model

    async def latest_test_run(self, session_id: str) -> ResearchLabTestRunModel | None:
        result = await self._session.execute(
            select(ResearchLabTestRunModel)
            .where(ResearchLabTestRunModel.session_id == session_id)
            .order_by(ResearchLabTestRunModel.started_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def append_terminal_events(
        self,
        *,
        session_id: str,
        test_run_id: str | None,
        events: list[SandboxTerminalEvent],
    ) -> list[ResearchLabTerminalEventModel]:
        sequence = await self.next_terminal_sequence(session_id)
        models = []
        for event in events:
            model = ResearchLabTerminalEventModel(
                id=str(uuid4()),
                session_id=session_id,
                test_run_id=test_run_id,
                sequence=sequence,
                stream=event.stream,
                line=event.line,
            )
            sequence += 1
            self._session.add(model)
            models.append(model)
        await self._session.flush()
        return models

    async def next_terminal_sequence(self, session_id: str) -> int:
        result = await self._session.execute(
            select(func.max(ResearchLabTerminalEventModel.sequence)).where(
                ResearchLabTerminalEventModel.session_id == session_id
            )
        )
        max_sequence = result.scalar_one_or_none()
        return int(max_sequence or 0) + 1

    async def list_terminal_events(
        self, session_id: str, after_sequence: int | None
    ) -> list[ResearchLabTerminalEventModel]:
        statement = select(ResearchLabTerminalEventModel).where(
            ResearchLabTerminalEventModel.session_id == session_id
        )
        if after_sequence is not None:
            statement = statement.where(ResearchLabTerminalEventModel.sequence > after_sequence)
        result = await self._session.execute(
            statement.order_by(ResearchLabTerminalEventModel.sequence.asc())
        )
        return list(result.scalars().all())

    async def clear_runtime_state(self, session_id: str) -> None:
        await self._session.execute(
            delete(ResearchLabTerminalEventModel).where(
                ResearchLabTerminalEventModel.session_id == session_id
            )
        )
        await self._session.execute(
            delete(ResearchLabExploitVerificationModel).where(
                ResearchLabExploitVerificationModel.session_id == session_id
            )
        )
        await self._session.execute(
            delete(ResearchLabTransactionModel).where(
                ResearchLabTransactionModel.session_id == session_id
            )
        )
        await self._session.execute(
            delete(ResearchLabReportModel).where(ResearchLabReportModel.session_id == session_id)
        )
        await self._session.execute(
            delete(ResearchLabTestRunModel).where(
                ResearchLabTestRunModel.session_id == session_id
            )
        )
        await self._session.execute(
            delete(ResearchLabFileModel).where(ResearchLabFileModel.session_id == session_id)
        )
        await self._session.flush()

    async def get_completion(
        self, *, user_id: str, lab_id: str
    ) -> ResearchLabCompletionModel | None:
        result = await self._session.execute(
            select(ResearchLabCompletionModel).where(
                ResearchLabCompletionModel.user_id == user_id,
                ResearchLabCompletionModel.lab_id == lab_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_completion(
        self,
        *,
        user_id: str,
        lab_id: str,
        lab_slug: str,
        session_id: str,
        xp_awarded: int,
        completed_at: datetime,
    ) -> ResearchLabCompletionModel:
        model = ResearchLabCompletionModel(
            id=str(uuid4()),
            user_id=user_id,
            lab_id=lab_id,
            lab_slug=lab_slug,
            session_id=session_id,
            xp_awarded=xp_awarded,
            completed_at=completed_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return model

    async def create_transaction(
        self,
        *,
        session_id: str,
        transaction_ref: str,
        instruction_type: str,
        parameters: dict,
        execution_status: str,
        logs: list[str],
        submitted_at: datetime,
        idempotency_key: str,
    ) -> ResearchLabTransactionModel:
        # Lock the session row to prevent concurrent history corruption
        stmt_lock = select(ResearchLabSessionModel).where(ResearchLabSessionModel.id == session_id).with_for_update()
        await self._session.execute(stmt_lock)

        stmt_seq = select(func.max(ResearchLabTransactionModel.sequence_number)).where(
            ResearchLabTransactionModel.session_id == session_id
        )
        max_seq = (await self._session.execute(stmt_seq)).scalar() or 0

        model = ResearchLabTransactionModel(
            id=str(uuid4()),
            session_id=session_id,
            transaction_ref=transaction_ref,
            instruction_type=instruction_type,
            parameters_json=parameters,
            execution_status=execution_status,
            logs_json=logs,
            submitted_at=submitted_at,
            idempotency_key=idempotency_key,
            sequence_number=max_seq + 1,
        )
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            if "idempotency_key" in str(exc) or "transaction_ref" in str(exc) or "sequence_number" in str(exc):
                raise ConflictError("Duplicate transaction: idempotency key already exists for this session") from exc
            raise
        await self._session.refresh(model)
        return model

    async def list_transactions(self, session_id: str) -> list[ResearchLabTransactionModel]:
        result = await self._session.execute(
            select(ResearchLabTransactionModel)
            .where(ResearchLabTransactionModel.session_id == session_id)
            .order_by(ResearchLabTransactionModel.submitted_at.asc())
        )
        return list(result.scalars().all())

    async def get_transaction(
        self, session_id: str, transaction_ref: str
    ) -> ResearchLabTransactionModel | None:
        result = await self._session.execute(
            select(ResearchLabTransactionModel).where(
                ResearchLabTransactionModel.session_id == session_id,
                ResearchLabTransactionModel.transaction_ref == transaction_ref,
            )
        )
        return result.scalar_one_or_none()

    async def create_exploit_verification(
        self,
        *,
        session_id: str,
        objective_ref: str,
        passed: bool,
        evidence: dict,
        verified_at: datetime,
    ) -> ResearchLabExploitVerificationModel:
        model = ResearchLabExploitVerificationModel(
            id=str(uuid4()),
            session_id=session_id,
            objective_ref=objective_ref,
            passed=passed,
            evidence_json=evidence,
            verified_at=verified_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return model

    async def get_report(self, session_id: str) -> ResearchLabReportModel | None:
        result = await self._session.execute(
            select(ResearchLabReportModel).where(ResearchLabReportModel.session_id == session_id)
        )
        return result.scalar_one_or_none()

    async def upsert_report(
        self,
        *,
        session_id: str,
        user_id: str,
        lab_id: str,
        status: str,
        fields: dict,
        feedback: str | None,
        validation_result: dict | None,
        submitted_at: datetime | None,
        accepted_at: datetime | None,
    ) -> ResearchLabReportModel:
        model = await self.get_report(session_id)
        if model is None:
            model = ResearchLabReportModel(
                id=str(uuid4()),
                session_id=session_id,
                user_id=user_id,
                lab_id=lab_id,
                status=status,
                fields_json=fields,
                feedback=feedback,
                validation_result_json=validation_result,
                submitted_at=submitted_at,
                accepted_at=accepted_at,
            )
            self._session.add(model)
        else:
            model.status = status
            model.fields_json = fields
            model.feedback = feedback
            model.validation_result_json = validation_result
            model.submitted_at = submitted_at
            model.accepted_at = accepted_at
        await self._session.flush()
        await self._session.refresh(model)
        return model
