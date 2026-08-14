from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.breach_rooms.infrastructure.database.models import (
    BreachRoomSubmissionModel,
)


class SQLAlchemyBreachRoomSubmissionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        room_id: str,
        user_id: str,
        wallet_address: str | None,
        title: str,
        category: str,
        severity: str,
        likelihood: str,
        source_reference: str,
        report_markdown: str,
    ) -> BreachRoomSubmissionModel:
        model = BreachRoomSubmissionModel(
            room_id=room_id,
            user_id=user_id,
            wallet_address=wallet_address,
            title=title,
            category=category,
            severity=severity,
            likelihood=likelihood,
            source_reference=source_reference,
            report_markdown=report_markdown,
            status="submitted",
            review_state="reviewing",
            pr_creation_status="pending",
            matched_findings_json=[],
            missed_findings_json=[],
            xp_earned=0,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return model

    async def list_for_user(
        self, *, room_id: str, user_id: str
    ) -> list[BreachRoomSubmissionModel]:
        result = await self._session.execute(
            select(BreachRoomSubmissionModel)
            .where(
                BreachRoomSubmissionModel.room_id == room_id,
                BreachRoomSubmissionModel.user_id == user_id,
            )
            .order_by(BreachRoomSubmissionModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def latest_for_user(
        self, *, room_id: str, user_id: str
    ) -> BreachRoomSubmissionModel | None:
        result = await self._session.execute(
            select(BreachRoomSubmissionModel)
            .where(
                BreachRoomSubmissionModel.room_id == room_id,
                BreachRoomSubmissionModel.user_id == user_id,
            )
            .order_by(BreachRoomSubmissionModel.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def mark_pr_created(
        self,
        submission: BreachRoomSubmissionModel,
        *,
        pr_url: str,
        pr_number: int | None,
        pr_branch: str,
        pr_file_path: str,
    ) -> BreachRoomSubmissionModel:
        submission.pr_url = pr_url
        submission.pr_number = pr_number
        submission.pr_branch = pr_branch
        submission.pr_file_path = pr_file_path
        submission.pr_creation_status = "created"
        submission.pr_creation_error = None
        await self._session.flush()
        await self._session.refresh(submission)
        return submission

    async def mark_pr_failed(
        self,
        submission: BreachRoomSubmissionModel,
        *,
        error: str,
        pr_branch: str,
        pr_file_path: str,
    ) -> BreachRoomSubmissionModel:
        submission.pr_branch = pr_branch
        submission.pr_file_path = pr_file_path
        submission.pr_creation_status = "failed"
        submission.pr_creation_error = error[:4000]
        await self._session.flush()
        await self._session.refresh(submission)
        return submission
