from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db_session
from app.core.exceptions.domain import DomainError
from app.modules.analytics.infrastructure.repositories.sqlalchemy_analytics_repository import (
    SQLAlchemyAnalyticsRepository,
)
from app.modules.beta_access.application.use_cases.beta_access import (
    GetBetaAccessStatusUseCase,
    RedeemBetaAccessCodeUseCase,
    RequestBetaAccessUseCase,
)
from app.modules.beta_access.infrastructure.repositories.sqlalchemy_beta_access_repository import (
    SQLAlchemyBetaAccessRepository,
)
from app.modules.beta_access.presentation.schemas.beta_access import (
    BetaAccessRedeemRequest,
    BetaAccessRequestCreateRequest,
    BetaAccessRequestResponse,
    BetaAccessStatusResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _access_failure_reason(exc: DomainError) -> str:
    return {
        "INVALID_ACCESS_CODE": "invalid",
        "EXPIRED_ACCESS_CODE": "expired",
        "EXHAUSTED_ACCESS_CODE": "exhausted",
        "WALLET_REQUIRED": "wallet_required",
    }.get(getattr(exc, "code", ""), "unknown")


@router.get(
    "/status",
    response_model=BetaAccessStatusResponse,
    response_model_by_alias=True,
    summary="Check beta access by wallet",
)
async def get_beta_access_status(
    wallet_address: str | None = Query(default=None),
    wallet_address_camel: str | None = Query(default=None, alias="walletAddress"),
    session: AsyncSession = Depends(get_db_session),
) -> BetaAccessStatusResponse:
    status_data = await GetBetaAccessStatusUseCase(
        SQLAlchemyBetaAccessRepository(session)
    ).execute(wallet_address or wallet_address_camel or "")
    analytics = SQLAlchemyAnalyticsRepository(session)
    await analytics.record(
        event_type="beta_access_status_checked",
        wallet_address=status_data["walletAddress"],
        subject_type="wallet",
        subject_id=status_data["walletAddress"],
        metadata={
            "status": status_data["status"],
            "hasAccess": status_data["hasAccess"],
            "accessSource": status_data["accessSource"],
        },
    )
    await session.commit()
    return BetaAccessStatusResponse.model_validate(status_data)


@router.post(
    "/requests",
    response_model=BetaAccessRequestResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
    summary="Request beta access",
)
async def request_beta_access(
    payload: BetaAccessRequestCreateRequest,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> BetaAccessRequestResponse:
    request_entry, already_requested = await RequestBetaAccessUseCase(
        SQLAlchemyBetaAccessRepository(session)
    ).execute(
        wallet_address=payload.wallet_address,
        contact=payload.contact,
        name_or_handle=payload.name_or_handle,
        interest=payload.interest,
        community_or_org=payload.community_or_org,
    )
    await SQLAlchemyAnalyticsRepository(session).record(
        event_type="beta_access_requested",
        wallet_address=request_entry.wallet_address,
        subject_type="beta_access_request",
        subject_id=request_entry.id,
        metadata={
            "status": request_entry.status.value,
            "alreadyRequested": already_requested,
            "hasContact": request_entry.contact is not None,
            "hasWallet": request_entry.wallet_address is not None,
        },
    )
    await session.commit()
    response.status_code = status.HTTP_200_OK if already_requested else status.HTTP_201_CREATED
    logger.info(
        "beta_access_request_saved",
        extra={
            "beta_access_request_id": request_entry.id,
            "wallet_address": request_entry.wallet_address,
            "has_contact": request_entry.contact is not None,
            "already_requested": already_requested,
        },
    )
    return BetaAccessRequestResponse(
        requestId=request_entry.id,
        status=request_entry.status.value,
        message=(
            "Beta access request already exists."
            if already_requested
            else "Beta access request received."
        ),
    )


@router.post(
    "/redeem",
    response_model=BetaAccessStatusResponse,
    response_model_by_alias=True,
    summary="Redeem beta access code",
)
async def redeem_beta_access_code(
    payload: BetaAccessRedeemRequest,
    session: AsyncSession = Depends(get_db_session),
) -> BetaAccessStatusResponse:
    analytics = SQLAlchemyAnalyticsRepository(session)
    await analytics.record(
        event_type="beta_access_code_submitted",
        wallet_address=payload.wallet_address,
        subject_type="wallet",
        subject_id=payload.wallet_address,
        metadata={"hasCode": True},
    )
    try:
        status_data = await RedeemBetaAccessCodeUseCase(
            SQLAlchemyBetaAccessRepository(session)
        ).execute(code=payload.code, wallet_address=payload.wallet_address)
    except DomainError as exc:
        await analytics.record(
            event_type="beta_access_code_failed",
            wallet_address=payload.wallet_address,
            subject_type="wallet",
            subject_id=payload.wallet_address,
            metadata={
                "failureReason": _access_failure_reason(exc),
                "errorCode": getattr(exc, "code", "DOMAIN_ERROR"),
            },
        )
        await analytics.record(
            event_type="beta_access_denied",
            wallet_address=payload.wallet_address,
            subject_type="wallet",
            subject_id=payload.wallet_address,
            metadata={
                "failureReason": _access_failure_reason(exc),
                "errorCode": getattr(exc, "code", "DOMAIN_ERROR"),
            },
        )
        await session.commit()
        raise
    await analytics.record(
        event_type="beta_access_code_redeemed",
        wallet_address=status_data["walletAddress"],
        subject_type="wallet",
        subject_id=status_data["walletAddress"],
        metadata={
            "status": status_data["status"],
            "accessSource": status_data["accessSource"],
        },
    )
    await analytics.record(
        event_type="beta_access_granted",
        wallet_address=status_data["walletAddress"],
        subject_type="wallet",
        subject_id=status_data["walletAddress"],
        metadata={
            "status": status_data["status"],
            "accessSource": status_data["accessSource"],
        },
    )
    await session.commit()
    logger.info(
        "beta_access_code_redeemed",
        extra={"wallet_address": status_data["walletAddress"], "status": status_data["status"]},
    )
    return BetaAccessStatusResponse.model_validate(status_data)
