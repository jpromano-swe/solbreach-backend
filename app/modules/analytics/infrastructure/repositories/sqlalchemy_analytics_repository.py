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
        session_id: str | None = None,
        lab_id: str | None = None,
        level_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        source: str = "backend",
        request_id: str | None = None,
        user_agent: str | None = None,
        ip_hash: str | None = None,
    ) -> AnalyticsEventModel:
        model = AnalyticsEventModel(
            id=str(uuid4()),
            user_id=user_id,
            wallet_address=wallet_address,
            event_type=event_type,
            subject_type=subject_type,
            subject_id=subject_id,
            session_id=session_id,
            lab_id=lab_id,
            level_id=level_id,
            source=source,
            request_id=request_id,
            user_agent=user_agent,
            ip_hash=ip_hash,
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
            "beta": {
                "walletConnected": await self._count_event("wallet_connected"),
                "accessGranted": await self._count_event("beta_access_granted"),
                "accessDenied": await self._count_event("beta_access_denied"),
                "requestsSubmitted": await self._count_event("beta_access_requested"),
                "codesRedeemed": await self._count_event("beta_access_code_redeemed"),
                "codesFailed": await self._count_event("beta_access_code_failed"),
                "appEntered": await self._count_event("beta_app_entered"),
            },
            "rl1": {
                "sessionsStarted": await self._count_event("research_lab_session_started"),
                "depositsSubmitted": await self._count_event("rl1_deposit_submitted"),
                "depositAccepted": await self._count_event("rl1_deposit_accepted"),
                "depositRejected": await self._count_event("rl1_deposit_rejected"),
                "borrowSubmitted": await self._count_event("rl1_borrow_submitted"),
                "borrowAccepted": await self._count_event("rl1_borrow_accepted"),
                "borrowRejected": await self._count_event("rl1_borrow_rejected"),
                "impactVerified": await self._count_event("rl1_impact_verified"),
                "impactRejected": await self._count_event("rl1_impact_rejected"),
                "reviewsPassed": await self._count_event("rl1_finding_review_passed"),
                "reviewsFailed": await self._count_event("rl1_finding_review_failed"),
                "reportsAccepted": await self._count_event("rl1_audit_report_accepted"),
                "reportsRejected": await self._count_event("rl1_audit_report_rejected"),
            },
            "dropoff": [
                {"step": "beta_app_entered", "count": await self._count_event("beta_app_entered")},
                {
                    "step": "research_lab_session_started",
                    "count": await self._count_event("research_lab_session_started"),
                },
                {"step": "rl1_impact_verified", "count": await self._count_event("rl1_impact_verified")},
                {
                    "step": "rl1_finding_review_passed",
                    "count": await self._count_event("rl1_finding_review_passed"),
                },
                {
                    "step": "rl1_audit_report_accepted",
                    "count": await self._count_event("rl1_audit_report_accepted"),
                },
            ],
        }

    async def list_events(
        self,
        *,
        wallet_address: str | None = None,
        lab_id: str | None = None,
        session_id: str | None = None,
        limit: int = 100,
    ) -> list[AnalyticsEventModel]:
        statement = select(AnalyticsEventModel)
        if wallet_address is not None:
            statement = statement.where(AnalyticsEventModel.wallet_address == wallet_address)
        if lab_id is not None:
            statement = statement.where(AnalyticsEventModel.lab_id == lab_id)
        if session_id is not None:
            statement = statement.where(AnalyticsEventModel.session_id == session_id)
        result = await self._session.execute(
            statement.order_by(AnalyticsEventModel.occurred_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def _count_event(self, event_type: str) -> int:
        result = await self._session.execute(
            select(func.count(AnalyticsEventModel.id)).where(
                AnalyticsEventModel.event_type == event_type
            )
        )
        return int(result.scalar_one() or 0)

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
