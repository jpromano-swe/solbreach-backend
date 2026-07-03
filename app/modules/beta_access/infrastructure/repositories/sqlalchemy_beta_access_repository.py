from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.beta_access.domain.entities.beta_access import (
    BetaAccessCode,
    BetaAccessCodeRedemption,
    BetaAccessCodeStatus,
    BetaAccessGrant,
    BetaAccessRequest,
    BetaAccessSource,
    BetaAccessStatus,
)
from app.modules.beta_access.domain.repositories.beta_access_repository import (
    BetaAccessRepository,
)
from app.modules.beta_access.infrastructure.database.models import (
    BetaAccessCodeModel,
    BetaAccessCodeRedemptionModel,
    BetaAccessGrantModel,
    BetaAccessRequestModel,
)


class SQLAlchemyBetaAccessRepository(BetaAccessRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_grant_by_wallet(self, wallet_address: str) -> BetaAccessGrant | None:
        result = await self._session.execute(
            select(BetaAccessGrantModel).where(
                BetaAccessGrantModel.wallet_address == wallet_address
            )
        )
        model = result.scalar_one_or_none()
        return self._grant_to_entity(model) if model else None

    async def create_grant(self, grant: BetaAccessGrant) -> BetaAccessGrant:
        model = BetaAccessGrantModel(
            id=grant.id,
            wallet_address=grant.wallet_address,
            user_id=grant.user_id,
            status=grant.status.value,
            source=grant.source.value,
            access_code_id=grant.access_code_id,
            revoked_at=grant.revoked_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._grant_to_entity(model)

    async def update_grant(self, grant: BetaAccessGrant) -> BetaAccessGrant:
        model = await self._session.get(BetaAccessGrantModel, grant.id)
        if model is None:
            raise ValueError("Beta access grant model not found")
        model.wallet_address = grant.wallet_address
        model.user_id = grant.user_id
        model.status = grant.status.value
        model.source = grant.source.value
        model.access_code_id = grant.access_code_id
        model.revoked_at = grant.revoked_at
        await self._session.flush()
        await self._session.refresh(model)
        return self._grant_to_entity(model)

    async def get_request_by_wallet(self, wallet_address: str) -> BetaAccessRequest | None:
        result = await self._session.execute(
            select(BetaAccessRequestModel).where(
                BetaAccessRequestModel.wallet_address == wallet_address
            )
        )
        model = result.scalar_one_or_none()
        return self._request_to_entity(model) if model else None

    async def get_request_by_normalized_contact(
        self, normalized_contact: str
    ) -> BetaAccessRequest | None:
        result = await self._session.execute(
            select(BetaAccessRequestModel).where(
                BetaAccessRequestModel.normalized_contact == normalized_contact
            )
        )
        model = result.scalar_one_or_none()
        return self._request_to_entity(model) if model else None

    async def create_request(self, request: BetaAccessRequest) -> BetaAccessRequest:
        model = BetaAccessRequestModel(
            id=request.id,
            wallet_address=request.wallet_address,
            contact=request.contact,
            normalized_contact=request.normalized_contact,
            name_or_handle=request.name_or_handle,
            interest=request.interest,
            community_or_org=request.community_or_org,
            status=request.status.value,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._request_to_entity(model)

    async def update_request(self, request: BetaAccessRequest) -> BetaAccessRequest:
        model = await self._session.get(BetaAccessRequestModel, request.id)
        if model is None:
            raise ValueError("Beta access request model not found")
        model.wallet_address = request.wallet_address
        model.contact = request.contact
        model.normalized_contact = request.normalized_contact
        model.name_or_handle = request.name_or_handle
        model.interest = request.interest
        model.community_or_org = request.community_or_org
        model.status = request.status.value
        await self._session.flush()
        await self._session.refresh(model)
        return self._request_to_entity(model)

    async def get_code_by_hash(self, code_hash: str) -> BetaAccessCode | None:
        result = await self._session.execute(
            select(BetaAccessCodeModel).where(BetaAccessCodeModel.code_hash == code_hash)
        )
        model = result.scalar_one_or_none()
        return self._code_to_entity(model) if model else None

    async def get_code_by_hash_for_update(self, code_hash: str) -> BetaAccessCode | None:
        result = await self._session.execute(
            select(BetaAccessCodeModel)
            .where(BetaAccessCodeModel.code_hash == code_hash)
            .with_for_update()
        )
        model = result.scalar_one_or_none()
        return self._code_to_entity(model) if model else None

    async def update_code(self, code: BetaAccessCode) -> BetaAccessCode:
        model = await self._session.get(BetaAccessCodeModel, code.id)
        if model is None:
            raise ValueError("Beta access code model not found")
        model.code_hash = code.code_hash
        model.label = code.label
        model.status = code.status.value
        model.max_redemptions = code.max_redemptions
        model.redemption_count = code.redemption_count
        model.expires_at = code.expires_at
        await self._session.flush()
        await self._session.refresh(model)
        return self._code_to_entity(model)

    async def get_redemption(
        self, *, code_id: str, wallet_address: str
    ) -> BetaAccessCodeRedemption | None:
        result = await self._session.execute(
            select(BetaAccessCodeRedemptionModel).where(
                BetaAccessCodeRedemptionModel.code_id == code_id,
                BetaAccessCodeRedemptionModel.wallet_address == wallet_address,
            )
        )
        model = result.scalar_one_or_none()
        return self._redemption_to_entity(model) if model else None

    async def create_redemption(
        self, redemption: BetaAccessCodeRedemption
    ) -> BetaAccessCodeRedemption:
        model = BetaAccessCodeRedemptionModel(
            id=redemption.id,
            code_id=redemption.code_id,
            wallet_address=redemption.wallet_address,
            user_id=redemption.user_id,
            redeemed_at=redemption.redeemed_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._redemption_to_entity(model)

    @staticmethod
    def _grant_to_entity(model: BetaAccessGrantModel) -> BetaAccessGrant:
        return BetaAccessGrant(
            id=model.id,
            wallet_address=model.wallet_address,
            user_id=model.user_id,
            status=BetaAccessStatus(model.status),
            source=BetaAccessSource(model.source),
            access_code_id=model.access_code_id,
            revoked_at=model.revoked_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _request_to_entity(model: BetaAccessRequestModel) -> BetaAccessRequest:
        return BetaAccessRequest(
            id=model.id,
            wallet_address=model.wallet_address,
            contact=model.contact,
            normalized_contact=model.normalized_contact,
            name_or_handle=model.name_or_handle,
            interest=model.interest,
            community_or_org=model.community_or_org,
            status=BetaAccessStatus(model.status),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _code_to_entity(model: BetaAccessCodeModel) -> BetaAccessCode:
        return BetaAccessCode(
            id=model.id,
            code_hash=model.code_hash,
            label=model.label,
            status=BetaAccessCodeStatus(model.status),
            max_redemptions=model.max_redemptions,
            redemption_count=model.redemption_count,
            expires_at=model.expires_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _redemption_to_entity(
        model: BetaAccessCodeRedemptionModel,
    ) -> BetaAccessCodeRedemption:
        return BetaAccessCodeRedemption(
            id=model.id,
            code_id=model.code_id,
            wallet_address=model.wallet_address,
            user_id=model.user_id,
            redeemed_at=model.redeemed_at,
        )
