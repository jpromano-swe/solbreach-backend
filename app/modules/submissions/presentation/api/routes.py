from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db_session
from app.core.dependencies.auth import get_current_user
from app.modules.submissions.application.use_cases.list_user_submissions import (
    ListUserSubmissionsUseCase,
)
from app.modules.submissions.domain.entities.submission import Submission
from app.modules.submissions.infrastructure.repositories.sqlalchemy_submission_repository import (
    SQLAlchemySubmissionRepository,
)
from app.modules.submissions.presentation.schemas.submission import (
    SubmissionResponse,
)
from app.modules.users.domain.entities.user import User
from app.shared.schemas.pagination import PageParams

router = APIRouter()


def _response(submission: Submission) -> SubmissionResponse:
    return SubmissionResponse.model_validate(submission, from_attributes=True)


@router.get("/me", response_model=list[SubmissionResponse])
async def list_my_submissions(
    page: PageParams = Depends(),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[SubmissionResponse]:
    submissions = await ListUserSubmissionsUseCase(SQLAlchemySubmissionRepository(session)).execute(
        current_user.id, page.limit, page.offset
    )
    return [_response(submission) for submission in submissions]
