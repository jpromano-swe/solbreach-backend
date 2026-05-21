from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db_session
from app.core.dependencies.auth import require_roles
from app.modules.users.domain.entities.user import User, UserRole
from app.modules.vulnerabilities.application.use_cases.create_vulnerability import (
    CreateVulnerabilityUseCase,
)
from app.modules.vulnerabilities.application.use_cases.list_vulnerabilities import (
    ListVulnerabilitiesUseCase,
)
from app.modules.vulnerabilities.domain.entities.vulnerability import Vulnerability
from app.modules.vulnerabilities.infrastructure.repositories import (
    sqlalchemy_vulnerability_repository,
)
from app.modules.vulnerabilities.presentation.schemas.vulnerability import (
    VulnerabilityCreateRequest,
    VulnerabilityResponse,
)
from app.shared.schemas.pagination import PageParams

router = APIRouter()


def _response(vulnerability: Vulnerability) -> VulnerabilityResponse:
    return VulnerabilityResponse.model_validate(vulnerability, from_attributes=True)


@router.get("", response_model=list[VulnerabilityResponse])
async def list_vulnerabilities(
    page: PageParams = Depends(),
    session: AsyncSession = Depends(get_db_session),
) -> list[VulnerabilityResponse]:
    repo = sqlalchemy_vulnerability_repository.SQLAlchemyVulnerabilityRepository(session)
    items = await ListVulnerabilitiesUseCase(repo).execute(page.limit, page.offset)
    return [_response(item) for item in items]


@router.post("", response_model=VulnerabilityResponse, status_code=status.HTTP_201_CREATED)
async def create_vulnerability(
    payload: VulnerabilityCreateRequest,
    _: User = Depends(require_roles([UserRole.ADMIN, UserRole.MODERATOR])),
    session: AsyncSession = Depends(get_db_session),
) -> VulnerabilityResponse:
    repo = sqlalchemy_vulnerability_repository.SQLAlchemyVulnerabilityRepository(session)
    item = await CreateVulnerabilityUseCase(repo).execute(
        slug=payload.slug,
        title=payload.title,
        category=payload.category,
        difficulty=payload.difficulty,
        description=payload.description,
        tags=payload.tags,
    )
    await session.commit()
    return _response(item)
