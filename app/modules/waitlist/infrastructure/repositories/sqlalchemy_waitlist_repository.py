from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.waitlist.domain.entities.waitlist_entry import WaitlistContactType, WaitlistEntry
from app.modules.waitlist.domain.repositories.waitlist_repository import WaitlistRepository
from app.modules.waitlist.infrastructure.database.models import WaitlistEntryModel


class SQLAlchemyWaitlistRepository(WaitlistRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, entry: WaitlistEntry) -> WaitlistEntry:
        model = WaitlistEntryModel(
            id=entry.id,
            name_or_handle=entry.name_or_handle,
            contact=entry.contact,
            normalized_contact=entry.normalized_contact,
            contact_type=entry.contact_type.value,
            is_solana_dev=entry.is_solana_dev,
            community_or_org=entry.community_or_org,
            interests_json=entry.interests,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def update(self, entry: WaitlistEntry) -> WaitlistEntry:
        model = await self._session.get(WaitlistEntryModel, entry.id)
        if model is None:
            raise ValueError("Waitlist entry model not found")
        model.name_or_handle = entry.name_or_handle
        model.contact = entry.contact
        model.normalized_contact = entry.normalized_contact
        model.contact_type = entry.contact_type.value
        model.is_solana_dev = entry.is_solana_dev
        model.community_or_org = entry.community_or_org
        model.interests_json = entry.interests
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def get_by_normalized_contact(self, normalized_contact: str) -> WaitlistEntry | None:
        result = await self._session.execute(
            select(WaitlistEntryModel).where(
                WaitlistEntryModel.normalized_contact == normalized_contact
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list(
        self,
        *,
        limit: int,
        offset: int,
        is_solana_dev: bool | None = None,
        interest: str | None = None,
    ) -> list[WaitlistEntry]:
        stmt = select(WaitlistEntryModel).order_by(WaitlistEntryModel.created_at.desc())
        if is_solana_dev is not None:
            stmt = stmt.where(WaitlistEntryModel.is_solana_dev == is_solana_dev)
        result = await self._session.execute(stmt.limit(limit).offset(offset))
        items = [self._to_entity(model) for model in result.scalars().all()]
        if interest is None:
            return items
        return [item for item in items if interest in item.interests]

    @staticmethod
    def _to_entity(model: WaitlistEntryModel) -> WaitlistEntry:
        return WaitlistEntry(
            id=model.id,
            name_or_handle=model.name_or_handle,
            contact=model.contact,
            normalized_contact=model.normalized_contact,
            contact_type=WaitlistContactType(model.contact_type),
            is_solana_dev=model.is_solana_dev,
            community_or_org=model.community_or_org,
            interests=list(model.interests_json or []),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
