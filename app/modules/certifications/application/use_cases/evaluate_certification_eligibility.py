from datetime import UTC, datetime
from uuid import uuid4

from app.core.config.settings import get_settings
from app.modules.certifications.domain.certificate_definitions import (
    CERTIFICATE_DEFINITIONS,
    LEVEL_ORDER_TO_CERTIFICATE_ID,
    absolute_certificate_url,
)
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
        canonical_certification = await self._evaluate_level_certifications(user_id)
        if _completed_level_order(canonical_certification) in {4, 5}:
            return canonical_certification
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
                return level_2_certification or canonical_certification

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

    async def _evaluate_level_certifications(self, user_id: str) -> Certification | None:
        latest_created: Certification | None = None
        for level_order in sorted(LEVEL_ORDER_TO_CERTIFICATE_ID):
            level = await self._levels.get_by_order(level_order)
            if level is None:
                continue
            if await self._progress.get_for_user_level(user_id, level.id) is None:
                continue
            certificate_id = LEVEL_ORDER_TO_CERTIFICATE_ID[level_order]
            existing = await self._certifications.get_for_user_slug(user_id, certificate_id)
            if existing is not None:
                latest_created = existing
                continue
            definition = CERTIFICATE_DEFINITIONS[certificate_id]
            base_url = get_settings().app_base_url
            certification = await self._certifications.create(
                Certification(
                    id=str(uuid4()),
                    user_id=user_id,
                    slug=definition.certificate_id,
                    title=definition.title,
                    description=definition.description,
                    metadata={
                        "certificate_id": definition.certificate_id,
                        "certificate_number": definition.certificate_number,
                        "level": definition.level,
                        "completed_level_order": level.order,
                        "level_id": level.id,
                        "stage": "vulnerabilities",
                        "vulnerability_family": level.vulnerability_category,
                        "minting_enabled": True,
                        "metadata_uri": absolute_certificate_url(base_url, definition.metadata_path),
                        "image_uri": absolute_certificate_url(base_url, definition.image_path),
                    },
                    unlock_status=CertificationUnlockStatus.UNLOCKED,
                    mint_status=CertificationMintStatus.NOT_MINTED,
                    metadata_uri=absolute_certificate_url(base_url, definition.metadata_path),
                    unlocked_at=datetime.now(UTC),
                )
            )
            await self._events.publish(
                DomainEvent(
                    name="certification_unlocked",
                    payload={"user_id": user_id, "certification_slug": definition.certificate_id},
                )
            )
            latest_created = certification
        return latest_created

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


def _completed_level_order(certification: Certification | None) -> int | None:
    if certification is None:
        return None
    value = certification.metadata.get("completed_level_order") or certification.metadata.get("level")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
