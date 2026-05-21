from typing import Protocol

from app.modules.certifications.domain.entities.certification import Certification


class CertificationRepository(Protocol):
    async def create(self, certification: Certification) -> Certification: ...

    async def get_for_user_slug(self, user_id: str, slug: str) -> Certification | None: ...

    async def list_for_user(self, user_id: str, limit: int, offset: int) -> list[Certification]: ...
