from app.core.exceptions.domain import NotFoundError
from app.modules.users.domain.entities.user import User
from app.modules.users.domain.repositories.user_repository import UserRepository


class UserNotFoundError(NotFoundError):
    code = "USER_NOT_FOUND"


class GetUserUseCase:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def execute(self, user_id: str) -> User:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError("User not found")
        return user
