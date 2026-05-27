from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.labs.domain.entities.lab import Lab, LabStatus
from app.modules.labs.domain.repositories.lab_repository import LabRepository
from app.modules.labs.infrastructure.database.models import LabModel


class SQLAlchemyLabRepository(LabRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self, limit: int, offset: int) -> list[Lab]:
        result = await self._session.execute(
            select(LabModel)
            .where(LabModel.deleted_at.is_(None), LabModel.status == LabStatus.ACTIVE.value)
            .order_by(LabModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [self._to_entity(model) for model in result.scalars().all()]

    @staticmethod
    def _to_entity(model: LabModel) -> Lab:
        return Lab(
            id=model.id,
            slug=model.slug,
            title=model.title,
            description=model.description,
            status=LabStatus(model.status),
            sandbox_config=model.sandbox_config,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
