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
LEVEL_2_CERTIFICATION_SLUG = "static-pda-commander-hijack"
LEVEL_3_CERTIFICATION_SLUG = "arbitrary-cpi-delegated-signer-abuse"


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
        level_2_certification = await self._evaluate_level_2_certification(user_id)
        level_3_certification = await self._evaluate_level_3_certification(user_id)
        if level_3_certification is not None:
            return level_3_certification

        levels = [
            level
            for level in await self._levels.list_active_vulnerability_levels()
            if 0 <= level.order <= 3
        ]
        if not levels:
            return None

        for level in levels:
            if await self._progress.get_for_user_level(user_id, level.id) is None:
                return level_2_certification

        existing = await self._certifications.get_for_user_slug(
            user_id, BEGINNER_CERTIFICATION_SLUG
        )
        if existing is not None:
            return existing

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

    async def _evaluate_level_3_certification(self, user_id: str) -> Certification | None:
        existing = await self._certifications.get_for_user_slug(
            user_id, LEVEL_3_CERTIFICATION_SLUG
        )
        if existing is not None:
            return existing

        level_3 = await self._levels.get_by_order(3)
        if level_3 is None:
            return None
        if await self._progress.get_for_user_level(user_id, level_3.id) is None:
            return None

        certification = await self._certifications.create(
            Certification(
                id=str(uuid4()),
                user_id=user_id,
                slug=LEVEL_3_CERTIFICATION_SLUG,
                title="Arbitrary CPI Delegated Signer Abuse",
                description=(
                    "Unlocked by completing Level 3 and proving the arbitrary CPI target "
                    "plus delegated signer exploit flow with a wallet-signed devnet transaction."
                ),
                metadata={
                    "completed_level_order": level_3.order,
                    "level_id": level_3.id,
                    "stage": "vulnerabilities",
                    "minting_enabled": True,
                },
                unlock_status=CertificationUnlockStatus.UNLOCKED,
                mint_status=CertificationMintStatus.NOT_MINTED,
                unlocked_at=datetime.now(UTC),
            )
        )
        await self._events.publish(
            DomainEvent(
                name="certification_unlocked",
                payload={"user_id": user_id, "certification_slug": LEVEL_3_CERTIFICATION_SLUG},
            )
        )
        return certification

    async def _evaluate_level_2_certification(self, user_id: str) -> Certification | None:
        existing = await self._certifications.get_for_user_slug(
            user_id, LEVEL_2_CERTIFICATION_SLUG
        )
        if existing is not None:
            return existing

        level_2 = await self._levels.get_by_order(2)
        if level_2 is None:
            return None
        if await self._progress.get_for_user_level(user_id, level_2.id) is None:
            return None

        certification = await self._certifications.create(
            Certification(
                id=str(uuid4()),
                user_id=user_id,
                slug=LEVEL_2_CERTIFICATION_SLUG,
                title="Static PDA Commander Hijack",
                description=(
                    "Unlocked by completing Level 2 and proving the static PDA commander "
                    "hijack flow with a wallet-signed devnet transaction."
                ),
                metadata={
                    "completed_level_order": level_2.order,
                    "level_id": level_2.id,
                    "stage": "vulnerabilities",
                    "minting_enabled": True,
                },
                unlock_status=CertificationUnlockStatus.UNLOCKED,
                mint_status=CertificationMintStatus.NOT_MINTED,
                unlocked_at=datetime.now(UTC),
            )
        )
        await self._events.publish(
            DomainEvent(
                name="certification_unlocked",
                payload={"user_id": user_id, "certification_slug": LEVEL_2_CERTIFICATION_SLUG},
            )
        )
        return certification
