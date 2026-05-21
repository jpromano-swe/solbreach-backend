from datetime import UTC, datetime
from uuid import uuid4

from app.modules.certifications.domain.entities.certification import (
    Certification,
    CertificationMintStatus,
    CertificationUnlockStatus,
)
from app.modules.certifications.domain.repositories.certification_repository import (
    CertificationRepository,
)
from app.modules.levels.domain.repositories.level_repository import LevelRepository
from app.modules.progress.domain.repositories.progress_repository import ProgressRepository
from app.shared.events.event_bus import DomainEvent, EventPublisher

BEGINNER_CERTIFICATION_SLUG = "beginner-vulnerability-path"


class EvaluateCertificationEligibilityUseCase:
    def __init__(
        self,
        certifications: CertificationRepository,
        levels: LevelRepository,
        progress: ProgressRepository,
        events: EventPublisher,
    ) -> None:
        self._certifications = certifications
        self._levels = levels
        self._progress = progress
        self._events = events

    async def execute(self, user_id: str) -> Certification | None:
        existing = await self._certifications.get_for_user_slug(
            user_id, BEGINNER_CERTIFICATION_SLUG
        )
        if existing is not None:
            return existing

        levels = [
            level
            for level in await self._levels.list_active_vulnerability_levels()
            if 0 <= level.order <= 3
        ]
        if not levels:
            return None

        for level in levels:
            if await self._progress.get_for_user_level(user_id, level.id) is None:
                return None

        certification = await self._certifications.create(
            Certification(
                id=str(uuid4()),
                user_id=user_id,
                slug=BEGINNER_CERTIFICATION_SLUG,
                title="Beginner Vulnerability Path",
                description="Unlocked by completing SolBreach vulnerability Levels 0-3.",
                metadata={
                    "completed_level_orders": [level.order for level in levels],
                    "stage": "vulnerabilities",
                },
                unlock_status=CertificationUnlockStatus.UNLOCKED,
                mint_status=CertificationMintStatus.NOT_MINTED,
                unlocked_at=datetime.now(UTC),
            )
        )
        await self._events.publish(
            DomainEvent(
                name="certification_unlocked",
                payload={"user_id": user_id, "certification_slug": BEGINNER_CERTIFICATION_SLUG},
            )
        )
        return certification
