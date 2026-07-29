from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.onboarding.infrastructure.database.models import OnboardingResponseModel


class SQLAlchemyOnboardingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: str | None,
        wallet_address: str | None,
        schema_version: int,
        step: str | None,
        source: str,
        completed: bool,
        profile: str | None,
        real_experience: list[str],
        blockchain_security_profile: str | None,
        preferred_formats: list[str],
        security_learning_attempt: str | None,
        study_techniques: list[str],
        difficult_areas: list[str],
        hardest_practice_step: str | None,
        practice_signals: list[str],
        security_relevance: int | None,
        beta_intent: str | None,
        contact_name: str | None,
        preferred_contact_channel: str | None,
        contact: str | None,
        utm_source: str | None,
        utm_medium: str | None,
        utm_campaign: str | None,
        status: str,
        responses: dict | list,
        metadata: dict,
        request_id: str | None,
        user_agent: str | None,
    ) -> OnboardingResponseModel:
        model = OnboardingResponseModel(
            user_id=user_id,
            wallet_address=wallet_address,
            schema_version=schema_version,
            step=step,
            source=source,
            completed=completed,
            profile=profile,
            real_experience_json=real_experience,
            blockchain_security_profile=blockchain_security_profile,
            preferred_formats_json=preferred_formats,
            security_learning_attempt=security_learning_attempt,
            study_techniques_json=study_techniques,
            difficult_areas_json=difficult_areas,
            hardest_practice_step=hardest_practice_step,
            practice_signals_json=practice_signals,
            security_relevance=security_relevance,
            beta_intent=beta_intent,
            contact_name=contact_name,
            preferred_contact_channel=preferred_contact_channel,
            contact=contact,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            status=status,
            responses_json=responses,
            metadata_json=metadata,
            request_id=request_id,
            user_agent=user_agent,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return model

    async def latest_for_user_or_wallet(
        self,
        *,
        user_id: str | None,
        wallet_address: str | None,
    ) -> OnboardingResponseModel | None:
        stmt = select(OnboardingResponseModel).order_by(
            OnboardingResponseModel.created_at.desc()
        )
        if user_id is not None:
            stmt = stmt.where(OnboardingResponseModel.user_id == user_id)
        elif wallet_address is not None:
            stmt = stmt.where(OnboardingResponseModel.wallet_address == wallet_address)
        else:
            return None
        result = await self._session.execute(stmt.limit(1))
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        limit: int,
        offset: int,
        wallet_address: str | None = None,
        profile: str | None = None,
        blockchain_security_profile: str | None = None,
        preferred_format: str | None = None,
        security_learning_attempt: str | None = None,
        study_technique: str | None = None,
        difficult_area: str | None = None,
        security_relevance_min: int | None = None,
        security_relevance_max: int | None = None,
        beta_intent: str | None = None,
        status: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> list[OnboardingResponseModel]:
        stmt = select(OnboardingResponseModel).order_by(
            OnboardingResponseModel.created_at.desc()
        )
        if wallet_address is not None:
            stmt = stmt.where(OnboardingResponseModel.wallet_address == wallet_address)
        if profile is not None:
            stmt = stmt.where(OnboardingResponseModel.profile == profile)
        if blockchain_security_profile is not None:
            stmt = stmt.where(
                OnboardingResponseModel.blockchain_security_profile
                == blockchain_security_profile
            )
        if security_learning_attempt is not None:
            stmt = stmt.where(
                OnboardingResponseModel.security_learning_attempt
                == security_learning_attempt
            )
        if security_relevance_min is not None:
            stmt = stmt.where(
                OnboardingResponseModel.security_relevance >= security_relevance_min
            )
        if security_relevance_max is not None:
            stmt = stmt.where(
                OnboardingResponseModel.security_relevance <= security_relevance_max
            )
        if beta_intent is not None:
            stmt = stmt.where(OnboardingResponseModel.beta_intent == beta_intent)
        if status is not None:
            stmt = stmt.where(OnboardingResponseModel.status == status)
        if created_from is not None:
            stmt = stmt.where(OnboardingResponseModel.created_at >= created_from)
        if created_to is not None:
            stmt = stmt.where(OnboardingResponseModel.created_at <= created_to)

        result = await self._session.execute(stmt)
        items = list(result.scalars().all())
        if preferred_format is not None:
            items = [
                item
                for item in items
                if preferred_format in (item.preferred_formats_json or [])
            ]
        if study_technique is not None:
            items = [
                item
                for item in items
                if study_technique in (item.study_techniques_json or [])
            ]
        if difficult_area is not None:
            items = [
                item
                for item in items
                if difficult_area in (item.difficult_areas_json or [])
            ]
        return items[offset : offset + limit]
