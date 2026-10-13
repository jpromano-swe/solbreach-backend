import hashlib

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db_session
from app.core.dependencies.auth import require_roles
from app.modules.analytics.infrastructure.repositories.sqlalchemy_analytics_repository import (
    SQLAlchemyAnalyticsRepository,
)
from app.modules.analytics.presentation.schemas.analytics import AnalyticsEventCreateRequest
from app.modules.users.domain.entities.user import User, UserRole

router = APIRouter()


def _ip_hash(request: Request) -> str | None:
    host = request.client.host if request.client else None
    if not host:
        return None
    return hashlib.sha256(host.encode("utf-8")).hexdigest()


def _event_payload(event) -> dict:  # type: ignore[no-untyped-def]
    return {
        "id": event.id,
        "eventName": event.event_type,
        "walletAddress": event.wallet_address,
        "userId": event.user_id,
        "sessionId": event.session_id,
        "labId": event.lab_id,
        "levelId": event.level_id,
        "source": event.source,
        "properties": event.metadata_json,
        "requestId": event.request_id,
        "createdAt": event.occurred_at.isoformat(),
    }


@router.post(
    "/events",
    summary="Record frontend analytics event",
    description="Accepts UI-only funnel events. Backend-owned events are emitted by use cases.",
)
async def create_event(
    payload: AnalyticsEventCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    event = await SQLAlchemyAnalyticsRepository(session).record(
        event_type=payload.event_name,
        wallet_address=payload.wallet_address,
        session_id=payload.session_id,
        lab_id=payload.lab_id,
        level_id=payload.level_id,
        subject_type="frontend_event",
        subject_id=payload.session_id or payload.lab_id or payload.level_id,
        metadata=payload.properties,
        source="frontend",
        request_id=getattr(request.state, "request_id", None),
        user_agent=request.headers.get("user-agent"),
        ip_hash=_ip_hash(request),
    )
    await session.commit()
    return {"success": True, "data": _event_payload(event), "error": None}


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


@router.get(
    "/admin/funnel",
    summary="Get SolBreach beta/RL1 funnel analytics",
)
async def admin_funnel(
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.MODERATOR])),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    _ = current_user
    return {
        "success": True,
        "data": await SQLAlchemyAnalyticsRepository(session).funnel(),
        "error": None,
    }


@router.get(
    "/admin/events",
    summary="Export analytics events",
)
async def admin_events(
    wallet_address: str | None = Query(default=None),
    lab_id: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.MODERATOR])),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    _ = current_user
    events = await SQLAlchemyAnalyticsRepository(session).list_events(
        wallet_address=wallet_address,
        lab_id=lab_id,
        session_id=session_id,
        limit=limit,
    )
    return {"success": True, "data": [_event_payload(event) for event in events], "error": None}
