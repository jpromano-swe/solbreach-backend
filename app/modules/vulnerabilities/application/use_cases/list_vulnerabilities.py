from app.modules.vulnerabilities.domain.entities.vulnerability import Vulnerability
from app.modules.vulnerabilities.domain.repositories.vulnerability_repository import (
    VulnerabilityRepository,
)


class ListVulnerabilitiesUseCase:
    def __init__(self, vulnerabilities: VulnerabilityRepository) -> None:
        self._vulnerabilities = vulnerabilities

    async def execute(self, limit: int, offset: int) -> list[Vulnerability]:
        return await self._vulnerabilities.list(limit, offset)
