from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.certifications.domain.entities.certification import (
    Certification,
    CertificationMintStatus,
    CertificationUnlockStatus,
)
from app.modules.certifications.domain.repositories.certification_repository import (
    CertificationRepository,
)
from app.modules.certifications.infrastructure.database.models import CertificationModel


class SQLAlchemyCertificationRepository(CertificationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, certification: Certification) -> Certification:
        model = CertificationModel(
            id=certification.id,
            user_id=certification.user_id,
            slug=certification.slug,
            title=certification.title,
            description=certification.description,
            metadata_json=certification.metadata,
            unlock_status=certification.unlock_status.value,
            mint_status=certification.mint_status.value,
            unlocked_at=certification.unlocked_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def get_for_user_slug(self, user_id: str, slug: str) -> Certification | None:
        result = await self._session.execute(
            select(CertificationModel).where(
                CertificationModel.user_id == user_id,
                CertificationModel.slug == slug,
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_for_user(self, user_id: str, limit: int, offset: int) -> list[Certification]:
        result = await self._session.execute(
            select(CertificationModel)
            .where(CertificationModel.user_id == user_id)
            .order_by(CertificationModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [self._to_entity(model) for model in result.scalars().all()]

    @staticmethod
    def _to_entity(model: CertificationModel) -> Certification:
        return Certification(
            id=model.id,
            user_id=model.user_id,
            slug=model.slug,
            title=model.title,
            description=model.description,
            metadata=model.metadata_json,
            unlock_status=CertificationUnlockStatus(model.unlock_status),
            mint_status=CertificationMintStatus(model.mint_status),
            unlocked_at=model.unlocked_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
