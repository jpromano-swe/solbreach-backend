from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.infrastructure.database.models import WalletAuthNonceModel


class SQLAlchemyWalletNonceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, *, wallet_address: str, nonce: str, message: str, expires_at: datetime
    ) -> WalletAuthNonceModel:
        model = WalletAuthNonceModel(
            wallet_address=wallet_address,
            nonce=nonce,
            message=message,
            expires_at=expires_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return model

    async def get_active(self, *, wallet_address: str, nonce: str) -> WalletAuthNonceModel | None:
        result = await self._session.execute(
            select(WalletAuthNonceModel).where(
                WalletAuthNonceModel.wallet_address == wallet_address,
                WalletAuthNonceModel.nonce == nonce,
                WalletAuthNonceModel.consumed_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        expires_at = model.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            return None
        return model

    async def consume(self, model: WalletAuthNonceModel) -> WalletAuthNonceModel:
        model.consumed_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(model)
        return model
