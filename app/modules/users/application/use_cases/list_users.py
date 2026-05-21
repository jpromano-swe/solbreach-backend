from app.modules.users.domain.entities.user import User
from app.modules.users.domain.repositories.user_repository import UserRepository


class ListUsersUseCase:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def execute(self, limit: int, offset: int) -> list[User]:
        return await self._users.list(limit=limit, offset=offset)
