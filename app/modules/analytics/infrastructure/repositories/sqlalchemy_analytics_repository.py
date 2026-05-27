from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analytics.infrastructure.database.models import AnalyticsEventModel
from app.modules.certifications.infrastructure.database.models import CertificationModel
from app.modules.levels.infrastructure.database.models import LevelModel
from app.modules.progress.infrastructure.database.models import ProgressModel
from app.modules.users.infrastructure.database.models import UserModel


class SQLAlchemyAnalyticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        event_type: str,
        user_id: str | None = None,
        wallet_address: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AnalyticsEventModel:
        model = AnalyticsEventModel(
            id=str(uuid4()),
            user_id=user_id,
            wallet_address=wallet_address,
            event_type=event_type,
            subject_type=subject_type,
            subject_id=subject_id,
            metadata_json=metadata or {},
            occurred_at=datetime.now(UTC),
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return model

    async def funnel(self) -> dict[str, Any]:
        levels = (
            await self._session.execute(select(LevelModel).order_by(LevelModel.order.asc()))
        ).scalars().all()

        level_rows = []
        for level in levels:
            started_users = await self._count_events(
                "level_started", "level", level.id, distinct_field=AnalyticsEventModel.user_id
            )
            setup_wallets = await self._count_events(
                "level_setup_ready",
                "level",
                level.id,
                distinct_field=AnalyticsEventModel.wallet_address,
            )
            completed_users = await self._count_progress(level.id, count_wallets=False)
            completed_wallets = await self._count_progress(level.id, count_wallets=True)
            level_rows.append(
                {
                    "level_id": level.id,
                    "slug": level.slug,
                    "order": level.order,
                    "title": level.title,
                    "started_users": started_users,
                    "setup_wallets": setup_wallets,
                    "completed_users": completed_users,
                    "completed_wallets": completed_wallets,
                }
            )

        certifications = await self._certification_counts()
        return {
            "levels": level_rows,
            "certifications": certifications,
        }

    async def _count_events(
        self,
        event_type: str,
        subject_type: str,
        subject_id: str,
        *,
        distinct_field,
    ) -> int:
        result = await self._session.execute(
            select(func.count(distinct(distinct_field))).where(
                AnalyticsEventModel.event_type == event_type,
                AnalyticsEventModel.subject_type == subject_type,
                AnalyticsEventModel.subject_id == subject_id,
                distinct_field.is_not(None),
            )
        )
        return int(result.scalar_one() or 0)

    async def _count_progress(self, level_id: str, *, count_wallets: bool) -> int:
        field = UserModel.wallet_address if count_wallets else ProgressModel.user_id
        result = await self._session.execute(
            select(func.count(distinct(field)))
            .select_from(ProgressModel)
            .join(UserModel, UserModel.id == ProgressModel.user_id)
            .where(ProgressModel.level_id == level_id, field.is_not(None))
        )
        return int(result.scalar_one() or 0)

    async def _certification_counts(self) -> list[dict[str, Any]]:
        result = await self._session.execute(
            select(
                CertificationModel.slug,
                CertificationModel.mint_status,
                func.count(distinct(CertificationModel.user_id)),
                func.count(distinct(UserModel.wallet_address)),
            )
            .join(UserModel, UserModel.id == CertificationModel.user_id)
            .group_by(CertificationModel.slug, CertificationModel.mint_status)
        )
        return [
            {
                "slug": slug,
                "mint_status": mint_status,
                "users": int(users or 0),
                "wallets": int(wallets or 0),
            }
            for slug, mint_status, users, wallets in result.all()
        ]
