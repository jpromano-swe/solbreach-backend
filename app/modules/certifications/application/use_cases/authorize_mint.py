from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.domain import ConflictError, DomainError, ForbiddenError
from app.core.security.solana_wallet import verify_solana_signature
from app.modules.certifications.infrastructure.database.models import (
    CertificateMintAuthorizationModel,
)
from app.modules.certifications.presentation.schemas.mint_authorization import (
    MintAuthorizationRequest,
)
from app.modules.users.domain.entities.user import User
from app.modules.users.infrastructure.database.models import UserModel


class MintRateLimitError(DomainError):
    status_code = 429
    code = "MINT_RATE_LIMIT"


async def authorize_mint(
    payload: MintAuthorizationRequest, user: User, session: AsyncSession
) -> dict:
    # Serialize attempts for this unique wallet across PostgreSQL workers.
    record = await session.scalar(
        select(UserModel).where(UserModel.id == user.id).with_for_update()
    )
    if record is None or record.wallet_address != payload.player:
        raise ForbiddenError("The session must belong to the certificate wallet")
    now = datetime.now(UTC)
    age = int(now.timestamp()) - payload.issued_at
    if age < -30 or age > 300:
        raise ForbiddenError("Mint authorization expired or is dated in the future")
    try:
        verify_solana_signature(payload.player, payload.signing_message(), payload.signature)
    except ValueError as exc:
        raise ForbiddenError("Invalid wallet signature") from exc
    used = await session.scalar(
        select(CertificateMintAuthorizationModel.id).where(
            CertificateMintAuthorizationModel.nonce == payload.nonce
        )
    )
    if used:
        raise ConflictError("Mint authorization has already been used; sign a new request")
    attempts = await session.scalar(
        select(func.count())
        .select_from(CertificateMintAuthorizationModel)
        .where(
            CertificateMintAuthorizationModel.wallet_address == payload.player,
            CertificateMintAuthorizationModel.created_at >= now - timedelta(minutes=10),
        )
    )
    if attempts >= 5:
        raise MintRateLimitError(
            "At most five certificate mint attempts per wallet every ten minutes"
        )
    session.add(
        CertificateMintAuthorizationModel(nonce=payload.nonce, wallet_address=payload.player)
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("Mint authorization has already been used") from exc
    # This attests to wallet authorization ONLY. The mint server must separately
    # verify completion against backend status or the on-chain certificate PDA.
    return {"authorized": True, "wallet_address": payload.player, "level": payload.level}
