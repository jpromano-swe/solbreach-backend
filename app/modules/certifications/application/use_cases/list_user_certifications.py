from app.modules.certifications.domain.entities.certification import Certification
from app.modules.certifications.domain.repositories.certification_repository import (
    CertificationRepository,
)


class ListUserCertificationsUseCase:
    def __init__(self, certifications: CertificationRepository) -> None:
        self._certifications = certifications

    async def execute(self, user_id: str, limit: int, offset: int) -> list[Certification]:
        return await self._certifications.list_for_user(user_id, limit, offset)
