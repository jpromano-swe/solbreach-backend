from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db_session
from app.core.dependencies.auth import get_current_user
from app.modules.analytics.infrastructure.repositories.sqlalchemy_analytics_repository import (
    SQLAlchemyAnalyticsRepository,
)
from app.modules.badges.application.use_cases.badges import (
    ListUserBadgesUseCase,
    MarkBadgeSeenUseCase,
)
from app.modules.badges.infrastructure.repositories.sqlalchemy_badge_repository import (
    SQLAlchemyBadgeRepository,
)
from app.modules.users.domain.entities.user import User

router = APIRouter()


@router.get("/me", summary="List my badges")
async def list_my_badges(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    data = await ListUserBadgesUseCase(
        SQLAlchemyBadgeRepository(session),
        SQLAlchemyAnalyticsRepository(session),
    ).execute(current_user)
    await session.commit()
    return data


@router.post("/{slug}/seen", summary="Mark badge as seen")
async def mark_badge_seen(
    slug: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    data = await MarkBadgeSeenUseCase(
        SQLAlchemyBadgeRepository(session),
        SQLAlchemyAnalyticsRepository(session),
    ).execute(current_user, slug)
    await session.commit()
    return data
