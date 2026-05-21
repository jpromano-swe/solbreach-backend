from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db_session
from app.core.dependencies.auth import get_current_user
from app.modules.certifications.application.use_cases.list_user_certifications import (
    ListUserCertificationsUseCase,
)
from app.modules.certifications.domain.entities.certification import Certification
from app.modules.certifications.infrastructure.repositories import (
    sqlalchemy_certification_repository,
)
from app.modules.certifications.presentation.schemas.certification import CertificationResponse
from app.modules.users.domain.entities.user import User
from app.shared.schemas.pagination import PageParams

router = APIRouter()


def _response(certification: Certification) -> CertificationResponse:
    return CertificationResponse.model_validate(certification, from_attributes=True)


@router.get("/me", response_model=list[CertificationResponse])
async def list_my_certifications(
    page: PageParams = Depends(),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[CertificationResponse]:
    certifications = await ListUserCertificationsUseCase(
        sqlalchemy_certification_repository.SQLAlchemyCertificationRepository(session)
    ).execute(current_user.id, page.limit, page.offset)
    return [_response(certification) for certification in certifications]
