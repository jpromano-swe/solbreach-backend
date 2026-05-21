from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db_session
from app.modules.labs.application.use_cases.list_labs import ListLabsUseCase
from app.modules.labs.domain.entities.lab import Lab
from app.modules.labs.infrastructure.repositories.sqlalchemy_lab_repository import (
    SQLAlchemyLabRepository,
)
from app.modules.labs.presentation.schemas.lab import LabResponse
from app.shared.schemas.pagination import PageParams

router = APIRouter()


def _response(lab: Lab) -> LabResponse:
    return LabResponse.model_validate(lab, from_attributes=True)


@router.get("", response_model=list[LabResponse])
async def list_labs(
    page: PageParams = Depends(),
    session: AsyncSession = Depends(get_db_session),
) -> list[LabResponse]:
    labs = await ListLabsUseCase(SQLAlchemyLabRepository(session)).execute(page.limit, page.offset)
    return [_response(lab) for lab in labs]
