from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db_session
from app.core.dependencies.auth import get_current_user
from app.modules.progress.application.use_cases.list_user_progress import ListUserProgressUseCase
from app.modules.progress.domain.entities.progress import Progress
from app.modules.progress.infrastructure.repositories.sqlalchemy_progress_repository import (
    SQLAlchemyProgressRepository,
)
from app.modules.progress.presentation.schemas.progress import ProgressResponse
from app.modules.users.domain.entities.user import User
from app.shared.schemas.pagination import PageParams

router = APIRouter()


def _response(progress: Progress) -> ProgressResponse:
    return ProgressResponse.model_validate(progress, from_attributes=True)


@router.get("/me", response_model=list[ProgressResponse])
async def list_my_progress(
    page: PageParams = Depends(),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[ProgressResponse]:
    progress = await ListUserProgressUseCase(SQLAlchemyProgressRepository(session)).execute(
        current_user.id, page.limit, page.offset
    )
    return [_response(item) for item in progress]
