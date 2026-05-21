from uuid import uuid4

from app.core.exceptions.domain import ConflictError
from app.core.security.password import PasswordHasher
from app.modules.auth.application.dto.auth_tokens import AuthTokens
from app.modules.auth.application.interfaces.token_service import TokenService
from app.modules.users.domain.entities.user import User, UserRole
from app.modules.users.domain.repositories.user_repository import UserRepository


class UserAlreadyExistsError(ConflictError):
    code = "USER_ALREADY_EXISTS"


class RegisterUserUseCase:
    def __init__(
        self,
        users: UserRepository,
        password_hasher: PasswordHasher,
        tokens: TokenService,
    ) -> None:
        self._users = users
        self._password_hasher = password_hasher
        self._tokens = tokens

    async def execute(self, username: str, email: str, password: str) -> tuple[User, AuthTokens]:
        if await self._users.get_by_email(email):
            raise UserAlreadyExistsError("Email is already registered")
        if await self._users.get_by_username(username):
            raise UserAlreadyExistsError("Username is already registered")

        user = User(
            id=str(uuid4()),
            username=username,
            email=email,
            hashed_password=self._password_hasher.hash(password),
            role=UserRole.USER,
            wallet_address=None,
            bio=None,
            avatar=None,
            xp=0,
            reputation_score=0,
            completed_levels=0,
        )
        created = await self._users.create(user)
        return created, self._issue_tokens(created)

    def _issue_tokens(self, user: User) -> AuthTokens:
        return AuthTokens(
            access_token=self._tokens.create_token(user.id, user.role.value, "access"),
            refresh_token=self._tokens.create_token(user.id, user.role.value, "refresh"),
        )
