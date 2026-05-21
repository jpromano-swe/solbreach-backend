from app.core.exceptions.domain import UnauthorizedError
from app.core.security.password import PasswordHasher
from app.modules.auth.application.dto.auth_tokens import AuthTokens
from app.modules.auth.application.interfaces.token_service import TokenService
from app.modules.users.domain.entities.user import User
from app.modules.users.domain.repositories.user_repository import UserRepository


class InvalidCredentialsError(UnauthorizedError):
    code = "INVALID_CREDENTIALS"


class LoginUserUseCase:
    def __init__(
        self,
        users: UserRepository,
        password_hasher: PasswordHasher,
        tokens: TokenService,
    ) -> None:
        self._users = users
        self._password_hasher = password_hasher
        self._tokens = tokens

    async def execute(self, email: str, password: str) -> tuple[User, AuthTokens]:
        user = await self._users.get_by_email(email)
        if user is None or not self._password_hasher.verify(password, user.hashed_password):
            raise InvalidCredentialsError("Invalid email or password")
        return user, AuthTokens(
            access_token=self._tokens.create_token(user.id, user.role.value, "access"),
            refresh_token=self._tokens.create_token(user.id, user.role.value, "refresh"),
        )
