from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db_session
from app.core.dependencies.auth import require_roles
from app.modules.analytics.infrastructure.repositories.sqlalchemy_analytics_repository import (
    SQLAlchemyAnalyticsRepository,
)
from app.modules.users.domain.entities.user import User, UserRole

router = APIRouter()


@router.get(
    "/funnel",
    summary="Get SolBreach funnel analytics",
    description=(
        "Returns wallet/user counts across level starts, setup, completions, and "
        "certification mint states for bottleneck analysis."
    ),
)
async def funnel(
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.MODERATOR])),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    _ = current_user
    return {
        "success": True,
        "data": await SQLAlchemyAnalyticsRepository(session).funnel(),
        "error": None,
    }
