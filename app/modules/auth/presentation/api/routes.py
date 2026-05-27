from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db_session
from app.core.dependencies.auth import get_current_user
from app.core.security.jwt import JWTService
from app.core.security.password import PasswordHasher
from app.modules.analytics.infrastructure.repositories.sqlalchemy_analytics_repository import (
    SQLAlchemyAnalyticsRepository,
)
from app.modules.auth.application.use_cases.login_user import LoginUserUseCase
from app.modules.auth.application.use_cases.refresh_token import RefreshTokenUseCase
from app.modules.auth.application.use_cases.register_user import RegisterUserUseCase
from app.modules.auth.application.use_cases.wallet_auth import WalletAuthUseCase
from app.modules.auth.infrastructure.repositories.sqlalchemy_wallet_nonce_repository import (
    SQLAlchemyWalletNonceRepository,
)
from app.modules.auth.presentation.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    WalletNonceRequest,
    WalletNonceResponse,
    WalletVerifyRequest,
)
from app.modules.users.domain.entities.user import User
from app.modules.users.infrastructure.repositories.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
)
from app.modules.users.presentation.schemas.user import UserResponse

router = APIRouter()


def _user_response(user: User) -> UserResponse:
    return UserResponse.model_validate(user, from_attributes=True)


def _token_response(tokens) -> TokenResponse:  # type: ignore[no-untyped-def]
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest, session: AsyncSession = Depends(get_db_session)
) -> AuthResponse:
    repo = SQLAlchemyUserRepository(session)
    use_case = RegisterUserUseCase(repo, PasswordHasher(), JWTService())
    user, tokens = await use_case.execute(payload.username, str(payload.email), payload.password)
    await session.commit()
    return AuthResponse(user=_user_response(user), tokens=_token_response(tokens))


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest, session: AsyncSession = Depends(get_db_session)
) -> AuthResponse:
    repo = SQLAlchemyUserRepository(session)
    use_case = LoginUserUseCase(repo, PasswordHasher(), JWTService())
    user, tokens = await use_case.execute(str(payload.email), payload.password)
    return AuthResponse(user=_user_response(user), tokens=_token_response(tokens))


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest, session: AsyncSession = Depends(get_db_session)
) -> TokenResponse:
    repo = SQLAlchemyUserRepository(session)
    tokens = await RefreshTokenUseCase(repo, JWTService()).execute(payload.refresh_token)
    return _token_response(tokens)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return _user_response(current_user)


@router.post("/wallet/nonce", response_model=WalletNonceResponse)
async def wallet_nonce(
    payload: WalletNonceRequest, session: AsyncSession = Depends(get_db_session)
) -> WalletNonceResponse:
    use_case = WalletAuthUseCase(
        SQLAlchemyUserRepository(session),
        SQLAlchemyWalletNonceRepository(session),
        SQLAlchemyAnalyticsRepository(session),
        JWTService(),
        PasswordHasher(),
    )
    data = await use_case.create_nonce(payload.wallet_address)
    await session.commit()
    return WalletNonceResponse(**data)


@router.post("/wallet/verify", response_model=AuthResponse)
async def wallet_verify(
    payload: WalletVerifyRequest, session: AsyncSession = Depends(get_db_session)
) -> AuthResponse:
    use_case = WalletAuthUseCase(
        SQLAlchemyUserRepository(session),
        SQLAlchemyWalletNonceRepository(session),
        SQLAlchemyAnalyticsRepository(session),
        JWTService(),
        PasswordHasher(),
    )
    user, tokens = await use_case.verify_wallet_login(
        wallet_address=payload.wallet_address,
        nonce=payload.nonce,
        signature=payload.signature,
    )
    await session.commit()
    return AuthResponse(user=_user_response(user), tokens=_token_response(tokens))


@router.post("/wallet/link", response_model=UserResponse)
async def wallet_link(
    payload: WalletVerifyRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    use_case = WalletAuthUseCase(
        SQLAlchemyUserRepository(session),
        SQLAlchemyWalletNonceRepository(session),
        SQLAlchemyAnalyticsRepository(session),
        JWTService(),
        PasswordHasher(),
    )
    user = await use_case.link_wallet(
        user=current_user,
        wallet_address=payload.wallet_address,
        nonce=payload.nonce,
        signature=payload.signature,
    )
    await session.commit()
    return _user_response(user)
