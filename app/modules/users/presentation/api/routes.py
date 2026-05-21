from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db_session
from app.core.dependencies.auth import get_current_user, require_roles
from app.modules.users.application.use_cases.get_user import GetUserUseCase
from app.modules.users.application.use_cases.list_users import ListUsersUseCase
from app.modules.users.domain.entities.user import User, UserRole
from app.modules.users.infrastructure.repositories.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
)
from app.modules.users.presentation.schemas.user import UserResponse
from app.shared.schemas.pagination import PageParams

router = APIRouter()


def _user_response(user: User) -> UserResponse:
    return UserResponse.model_validate(user, from_attributes=True)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return _user_response(current_user)


@router.get("", response_model=list[UserResponse])
async def list_users(
    page: PageParams = Depends(),
    _: User = Depends(require_roles([UserRole.ADMIN, UserRole.MODERATOR])),
    session: AsyncSession = Depends(get_db_session),
) -> list[UserResponse]:
    users = await ListUsersUseCase(SQLAlchemyUserRepository(session)).execute(
        page.limit, page.offset
    )
    return [_user_response(user) for user in users]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    _: User = Depends(require_roles([UserRole.ADMIN, UserRole.MODERATOR])),
    session: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    user = await GetUserUseCase(SQLAlchemyUserRepository(session)).execute(user_id)
    return _user_response(user)
