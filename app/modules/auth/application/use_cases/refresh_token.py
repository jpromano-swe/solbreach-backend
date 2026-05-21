from app.core.security.jwt import JWTService
from app.modules.auth.application.dto.auth_tokens import AuthTokens
from app.modules.users.application.use_cases.get_user import UserNotFoundError
from app.modules.users.domain.repositories.user_repository import UserRepository


class RefreshTokenUseCase:
    def __init__(self, users: UserRepository, tokens: JWTService) -> None:
        self._users = users
        self._tokens = tokens

    async def execute(self, refresh_token: str) -> AuthTokens:
        payload = self._tokens.decode(refresh_token, expected_type="refresh")
        user = await self._users.get_by_id(payload.sub)
        if user is None:
            raise UserNotFoundError("User not found")
        return AuthTokens(
            access_token=self._tokens.create_token(user.id, user.role.value, "access"),
            refresh_token=self._tokens.create_token(user.id, user.role.value, "refresh"),
        )
