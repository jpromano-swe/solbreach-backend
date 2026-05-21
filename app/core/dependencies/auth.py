from collections.abc import Sequence

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db_session
from app.core.exceptions.domain import ForbiddenError, UnauthorizedError
from app.core.security.jwt import JWTService
from app.modules.users.domain.entities.user import User, UserRole
from app.modules.users.infrastructure.repositories.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
)

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    if credentials is None:
        raise UnauthorizedError("Missing bearer token")
    payload = JWTService().decode(credentials.credentials, expected_type="access")
    user = await SQLAlchemyUserRepository(session).get_by_id(payload.sub)
    if user is None:
        raise UnauthorizedError("Invalid token subject")
    return user


def require_roles(allowed_roles: Sequence[UserRole]):
    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise ForbiddenError("Insufficient permissions")
        return current_user

    return dependency
