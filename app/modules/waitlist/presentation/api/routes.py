from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db_session
from app.core.dependencies.auth import require_roles
from app.modules.users.domain.entities.user import User, UserRole
from app.modules.waitlist.application.use_cases.create_waitlist_entry import (
    CreateWaitlistEntryUseCase,
)
from app.modules.waitlist.application.use_cases.list_waitlist_entries import (
    ListWaitlistEntriesUseCase,
)
from app.modules.waitlist.domain.entities.waitlist_entry import WaitlistEntry, WaitlistInterest
from app.modules.waitlist.infrastructure.repositories.sqlalchemy_waitlist_repository import (
    SQLAlchemyWaitlistRepository,
)
from app.modules.waitlist.presentation.schemas.waitlist import (
    WaitlistAPIResponse,
    WaitlistCreateRequest,
    WaitlistEntryResponse,
)
from app.shared.schemas.pagination import PageParams

logger = logging.getLogger(__name__)
router = APIRouter()


def _to_response(entry: WaitlistEntry, *, already_joined: bool) -> WaitlistEntryResponse:
    return WaitlistEntryResponse(
        id=entry.id,
        already_joined=already_joined,
        name_or_handle=entry.name_or_handle,
        contact=entry.contact,
        contact_type=entry.contact_type.value,
        is_solana_dev=entry.is_solana_dev,
        interests=entry.interests,
        community_or_org=entry.community_or_org,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


@router.post(
    "",
    response_model=WaitlistAPIResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Join SolBreach waitlist",
    description="Creates or refreshes a structured early-access waitlist entry from the landing page.",
)
async def create_waitlist_entry(
    payload: WaitlistCreateRequest,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> WaitlistAPIResponse:
    entry, already_joined = await CreateWaitlistEntryUseCase(
        SQLAlchemyWaitlistRepository(session)
    ).execute(
        name_or_handle=payload.name_or_handle,
        contact=payload.contact,
        is_solana_dev=payload.is_solana_dev,
        interests=[item.value for item in payload.interests],
        community_or_org=payload.community_or_org,
    )
    await session.commit()
    response.status_code = status.HTTP_200_OK if already_joined else status.HTTP_201_CREATED
    logger.info(
        "waitlist_entry_saved",
        extra={
            "waitlist_entry_id": entry.id,
            "contact_type": entry.contact_type.value,
            "is_solana_dev": entry.is_solana_dev,
            "interest_count": len(entry.interests),
            "already_joined": already_joined,
        },
    )
    return WaitlistAPIResponse(data=_to_response(entry, already_joined=already_joined))


@router.get(
    "",
    response_model=WaitlistAPIResponse,
    summary="List SolBreach waitlist entries",
    description="Returns newest-first waitlist entries for internal/admin review.",
)
async def list_waitlist_entries(
    page: PageParams = Depends(),
    is_solana_dev: bool | None = Query(default=None),
    interest: WaitlistInterest | None = Query(default=None),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.MODERATOR])),
    session: AsyncSession = Depends(get_db_session),
) -> WaitlistAPIResponse:
    _ = current_user
    entries = await ListWaitlistEntriesUseCase(SQLAlchemyWaitlistRepository(session)).execute(
        limit=page.limit,
        offset=page.offset,
        is_solana_dev=is_solana_dev,
        interest=interest.value if interest is not None else None,
    )
    return WaitlistAPIResponse(
        data=[_to_response(entry, already_joined=False) for entry in entries]
    )
