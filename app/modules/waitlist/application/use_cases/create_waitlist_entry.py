from __future__ import annotations

from uuid import uuid4

from app.core.exceptions.domain import ConflictError
from app.modules.waitlist.domain.entities.waitlist_entry import (
    WaitlistContactType,
    WaitlistEntry,
)
from app.modules.waitlist.domain.repositories.waitlist_repository import WaitlistRepository


def _normalize_text(value: str, *, max_length: int) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise ConflictError("Field cannot be empty")
    return normalized[:max_length]


def _normalize_optional_text(value: str | None, *, max_length: int) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.strip().split())
    return normalized[:max_length] if normalized else None


def infer_contact_type(contact: str) -> WaitlistContactType:
    if "@" in contact and "." in contact.split("@", 1)[-1]:
        return WaitlistContactType.EMAIL
    lowered = contact.lower()
    if lowered.startswith("https://t.me/") or lowered.startswith("t.me/"):
        return WaitlistContactType.TELEGRAM
    if lowered.startswith("https://x.com/") or lowered.startswith("x.com/"):
        return WaitlistContactType.X
    return WaitlistContactType.UNKNOWN


def normalize_contact(contact: str) -> tuple[str, str, WaitlistContactType]:
    normalized = contact.strip()
    if not normalized:
        raise ConflictError("Contact cannot be empty")
    normalized = normalized[:255]
    contact_type = infer_contact_type(normalized)
    if contact_type is WaitlistContactType.EMAIL:
        lowered = normalized.lower()
        if lowered.count("@") != 1 or lowered.startswith("@") or lowered.endswith("@"):
            raise ConflictError("Contact must be a valid email or handle")
        return lowered, lowered, contact_type
    compact = normalized.replace(" ", "")
    if len(compact) < 2:
        raise ConflictError("Contact must be a valid email or handle")
    return normalized, compact.lower(), contact_type


class CreateWaitlistEntryUseCase:
    def __init__(self, repository: WaitlistRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        name_or_handle: str,
        contact: str,
        is_solana_dev: bool,
        interests: list[str],
        community_or_org: str | None,
    ) -> tuple[WaitlistEntry, bool]:
        normalized_name = _normalize_text(name_or_handle, max_length=120)
        persisted_contact, normalized_contact, contact_type = normalize_contact(contact)
        normalized_community = _normalize_optional_text(community_or_org, max_length=160)
        deduped_interests = list(dict.fromkeys(interests))

        existing = await self._repository.get_by_normalized_contact(normalized_contact)
        if existing is None:
            entry = WaitlistEntry(
                id=str(uuid4()),
                name_or_handle=normalized_name,
                contact=persisted_contact,
                normalized_contact=normalized_contact,
                contact_type=contact_type,
                is_solana_dev=is_solana_dev,
                community_or_org=normalized_community,
                interests=deduped_interests,
            )
            return await self._repository.create(entry), False

        existing.name_or_handle = normalized_name
        existing.contact = persisted_contact
        existing.normalized_contact = normalized_contact
        existing.contact_type = contact_type
        existing.is_solana_dev = is_solana_dev
        if normalized_community is not None:
            existing.community_or_org = normalized_community
        existing.interests = list(dict.fromkeys([*existing.interests, *deduped_interests]))
        return await self._repository.update(existing), True
