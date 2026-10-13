from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.core.exceptions.domain import ConflictError, UnauthorizedError
from app.core.security.password import PasswordHasher
from app.core.security.solana_wallet import verify_solana_signature
from app.modules.analytics.infrastructure.repositories.sqlalchemy_analytics_repository import (
    SQLAlchemyAnalyticsRepository,
)
from app.modules.auth.application.dto.auth_tokens import AuthTokens
from app.modules.auth.application.interfaces.token_service import TokenService
from app.modules.auth.infrastructure.repositories.sqlalchemy_wallet_nonce_repository import (
    SQLAlchemyWalletNonceRepository,
)
from app.modules.users.domain.entities.user import User, UserRole
from app.modules.users.domain.repositories.user_repository import UserRepository


class WalletNonceInvalidError(UnauthorizedError):
    code = "WALLET_NONCE_INVALID"


class WalletAlreadyLinkedError(ConflictError):
    code = "WALLET_ALREADY_LINKED"


class WalletAuthUseCase:
    def __init__(
        self,
        users: UserRepository,
        nonces: SQLAlchemyWalletNonceRepository,
        analytics: SQLAlchemyAnalyticsRepository,
        tokens: TokenService,
        password_hasher: PasswordHasher,
    ) -> None:
        self._users = users
        self._nonces = nonces
        self._analytics = analytics
        self._tokens = tokens
        self._password_hasher = password_hasher

    async def create_nonce(self, wallet_address: str) -> dict:
        nonce = secrets.token_urlsafe(32)
        issued_at = datetime.now(UTC)
        expires_at = issued_at + timedelta(minutes=5)
        message = (
            "Sign in to SolBreach\n\n"
            f"Wallet: {wallet_address}\n"
            f"Nonce: {nonce}\n"
            f"Issued At: {issued_at.isoformat()}"
        )
        await self._nonces.create(
            wallet_address=wallet_address,
            nonce=nonce,
            message=message,
            expires_at=expires_at,
        )
        await self._analytics.record(
            event_type="wallet_connect_started",
            wallet_address=wallet_address,
            subject_type="wallet",
            subject_id=wallet_address,
        )
        await self._analytics.record(
            event_type="wallet_nonce_requested",
            wallet_address=wallet_address,
            subject_type="wallet",
            subject_id=wallet_address,
        )
        return {
            "wallet_address": wallet_address,
            "nonce": nonce,
            "message": message,
            "expires_at": expires_at.isoformat(),
        }

    async def verify_wallet_login(
        self, *, wallet_address: str, nonce: str, signature: str
    ) -> tuple[User, AuthTokens]:
        nonce_model = await self._nonces.get_active(wallet_address=wallet_address, nonce=nonce)
        if nonce_model is None:
            raise WalletNonceInvalidError("Wallet login nonce is invalid or expired")
        verify_solana_signature(wallet_address, nonce_model.message, signature)
        await self._nonces.consume(nonce_model)

        user = await self._users.get_by_wallet_address(wallet_address)
        user_created = user is None
        if user is None:
            user = await self._users.create(self._wallet_user(wallet_address))

        await self._analytics.record(
            event_type="wallet_login",
            user_id=user.id,
            wallet_address=wallet_address,
            subject_type="wallet",
            subject_id=wallet_address,
        )
        await self._analytics.record(
            event_type="wallet_connected",
            user_id=user.id,
            wallet_address=wallet_address,
            subject_type="wallet",
            subject_id=wallet_address,
            metadata={"userCreated": user_created},
        )
        await self._analytics.record(
            event_type="wallet_login_completed",
            user_id=user.id,
            wallet_address=wallet_address,
            subject_type="wallet",
            subject_id=wallet_address,
            metadata={"userCreated": user_created},
        )
        if user_created:
            await self._analytics.record(
                event_type="user_created",
                user_id=user.id,
                wallet_address=wallet_address,
                subject_type="wallet",
                subject_id=wallet_address,
                metadata={"source": "wallet_auth"},
            )
        return user, self._issue_tokens(user)

    async def link_wallet(
        self, *, user: User, wallet_address: str, nonce: str, signature: str
    ) -> User:
        nonce_model = await self._nonces.get_active(wallet_address=wallet_address, nonce=nonce)
        if nonce_model is None:
            raise WalletNonceInvalidError("Wallet link nonce is invalid or expired")
        verify_solana_signature(wallet_address, nonce_model.message, signature)

        existing = await self._users.get_by_wallet_address(wallet_address)
        if existing is not None and existing.id != user.id:
            raise WalletAlreadyLinkedError("Wallet is already linked to another user")

        await self._nonces.consume(nonce_model)
        user.wallet_address = wallet_address
        updated = await self._users.update(user)
        await self._analytics.record(
            event_type="wallet_linked",
            user_id=user.id,
            wallet_address=wallet_address,
            subject_type="wallet",
            subject_id=wallet_address,
        )
        return updated

    def _wallet_user(self, wallet_address: str) -> User:
        short = wallet_address[:12]
        return User(
            id=str(uuid4()),
            username=f"wallet_{short}",
            email=f"wallet_{wallet_address}@wallet.solbreach.app",
            hashed_password=self._password_hasher.hash(secrets.token_urlsafe(32)),
            role=UserRole.USER,
            wallet_address=wallet_address,
            bio=None,
            avatar=None,
            xp=0,
            reputation_score=0,
            completed_levels=0,
        )

    def _issue_tokens(self, user: User) -> AuthTokens:
        return AuthTokens(
            access_token=self._tokens.create_token(user.id, user.role.value, "access"),
            refresh_token=self._tokens.create_token(user.id, user.role.value, "refresh"),
        )
