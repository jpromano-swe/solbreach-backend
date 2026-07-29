from __future__ import annotations

import csv
from datetime import datetime
from io import StringIO

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db_session
from app.core.dependencies.auth import bearer_scheme, require_roles
from app.core.exceptions.domain import UnauthorizedError
from app.core.security.jwt import JWTService
from app.modules.analytics.infrastructure.repositories.sqlalchemy_analytics_repository import (
    SQLAlchemyAnalyticsRepository,
)
from app.modules.onboarding.infrastructure.database.models import OnboardingResponseModel
from app.modules.onboarding.infrastructure.repositories.sqlalchemy_onboarding_repository import (
    SQLAlchemyOnboardingRepository,
)
from app.modules.onboarding.presentation.schemas.onboarding import (
    BetaIntent,
    BlockchainSecurityProfile,
    DifficultArea,
    OnboardingAPIResponse,
    OnboardingProfile,
    OnboardingResponseCreateRequest,
    OnboardingResponseData,
    PreferredFormat,
    SecurityLearningAttempt,
    StudyTechnique,
)
from app.modules.users.domain.entities.user import User, UserRole
from app.modules.users.infrastructure.repositories.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
)
from app.shared.schemas.pagination import PageParams

router = APIRouter()


async def optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> User | None:
    if credentials is None:
        return None
    payload = JWTService().decode(credentials.credentials, expected_type="access")
    user = await SQLAlchemyUserRepository(session).get_by_id(payload.sub)
    if user is None:
        raise UnauthorizedError("Invalid token subject")
    return user


def _response_payload(model: OnboardingResponseModel) -> OnboardingResponseData:
    return OnboardingResponseData(
        id=model.id,
        walletAddress=model.wallet_address,
        userId=model.user_id,
        schemaVersion=model.schema_version,
        step=model.step,
        source=model.source,
        completed=model.completed,
        status=model.status,
        profile=model.profile,
        realExperience=list(model.real_experience_json or []),
        blockchainSecurityProfile=model.blockchain_security_profile,
        preferredFormats=list(model.preferred_formats_json or []),
        securityLearningAttempt=model.security_learning_attempt,
        studyTechniques=list(model.study_techniques_json or []),
        difficultAreas=list(model.difficult_areas_json or []),
        hardestPracticeStep=model.hardest_practice_step,
        practiceSignals=list(model.practice_signals_json or []),
        securityRelevance=model.security_relevance,
        betaIntent=model.beta_intent,
        contactName=model.contact_name,
        preferredContactChannel=model.preferred_contact_channel,
        contact=model.contact,
        utmSource=model.utm_source,
        utmMedium=model.utm_medium,
        utmCampaign=model.utm_campaign,
        responses=model.responses_json,
        metadata=model.metadata_json,
        createdAt=model.created_at,
        updatedAt=model.updated_at,
    )


def _enum_values(values: list[object] | None) -> list[str]:
    return [str(item) for item in (values or [])]


def _csv_response(items: list[OnboardingResponseModel]) -> Response:
    output = StringIO()
    columns = [
        "id",
        "schemaVersion",
        "profile",
        "realExperience",
        "blockchainSecurityProfile",
        "preferredFormats",
        "securityLearningAttempt",
        "studyTechniques",
        "difficultAreas",
        "hardestPracticeStep",
        "practiceSignals",
        "securityRelevance",
        "betaIntent",
        "contactName",
        "preferredContactChannel",
        "contact",
        "source",
        "utmSource",
        "utmMedium",
        "utmCampaign",
        "status",
        "createdAt",
        "updatedAt",
    ]
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for item in items:
        writer.writerow(
            {
                "id": item.id,
                "schemaVersion": item.schema_version,
                "profile": item.profile,
                "realExperience": ";".join(item.real_experience_json or []),
                "blockchainSecurityProfile": item.blockchain_security_profile,
                "preferredFormats": ";".join(item.preferred_formats_json or []),
                "securityLearningAttempt": item.security_learning_attempt,
                "studyTechniques": ";".join(item.study_techniques_json or []),
                "difficultAreas": ";".join(item.difficult_areas_json or []),
                "hardestPracticeStep": item.hardest_practice_step,
                "practiceSignals": ";".join(item.practice_signals_json or []),
                "securityRelevance": item.security_relevance,
                "betaIntent": item.beta_intent,
                "contactName": item.contact_name,
                "preferredContactChannel": item.preferred_contact_channel,
                "contact": item.contact,
                "source": item.source,
                "utmSource": item.utm_source,
                "utmMedium": item.utm_medium,
                "utmCampaign": item.utm_campaign,
                "status": item.status,
                "createdAt": item.created_at.isoformat(),
                "updatedAt": item.updated_at.isoformat(),
            }
        )
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=onboarding-responses.csv"},
    )


@router.post(
    "/responses",
    response_model=OnboardingAPIResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
    summary="Store beta onboarding question responses",
)
async def create_onboarding_response(
    payload: OnboardingResponseCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> OnboardingAPIResponse:
    wallet_address = payload.wallet_address
    user_id = None

    model = await SQLAlchemyOnboardingRepository(session).create(
        user_id=user_id,
        wallet_address=wallet_address,
        schema_version=payload.schema_version,
        step=payload.step,
        source=payload.source or "beta_onboarding",
        completed=payload.completed,
        profile=str(payload.profile) if payload.profile else None,
        real_experience=_enum_values(payload.real_experience),
        blockchain_security_profile=(
            str(payload.blockchain_security_profile)
            if payload.blockchain_security_profile
            else None
        ),
        preferred_formats=_enum_values(payload.preferred_formats),
        security_learning_attempt=(
            str(payload.security_learning_attempt)
            if payload.security_learning_attempt
            else None
        ),
        study_techniques=_enum_values(payload.study_techniques),
        difficult_areas=_enum_values(payload.difficult_areas),
        hardest_practice_step=payload.hardest_practice_step,
        practice_signals=_enum_values(payload.practice_signals),
        security_relevance=payload.security_relevance,
        beta_intent=str(payload.beta_intent) if payload.beta_intent else None,
        contact_name=payload.contact_name,
        preferred_contact_channel=(
            str(payload.preferred_contact_channel)
            if payload.preferred_contact_channel
            else None
        ),
        contact=payload.contact,
        utm_source=payload.utm_source,
        utm_medium=payload.utm_medium,
        utm_campaign=payload.utm_campaign,
        status=payload.status,
        responses=payload.normalized_responses(),
        metadata=payload.metadata,
        request_id=getattr(request.state, "request_id", None),
        user_agent=request.headers.get("user-agent"),
    )
    await SQLAlchemyAnalyticsRepository(session).record(
        event_type="onboarding_response_submitted",
        user_id=user_id,
        wallet_address=wallet_address,
        subject_type="onboarding_response",
        subject_id=model.id,
        metadata=payload.analytics_dimensions(),
        request_id=getattr(request.state, "request_id", None),
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    return OnboardingAPIResponse(data=_response_payload(model))


@router.get(
    "/responses/me",
    response_model=OnboardingAPIResponse,
    response_model_by_alias=True,
    summary="Get my latest onboarding response",
)
async def get_my_latest_onboarding_response(
    current_user: User = Depends(optional_current_user),
    wallet_address: str | None = Query(default=None, alias="walletAddress"),
    session: AsyncSession = Depends(get_db_session),
) -> OnboardingAPIResponse:
    if current_user is None and wallet_address is None:
        raise UnauthorizedError("Wallet address or bearer token is required")
    if current_user is not None and current_user.wallet_address is not None:
        wallet_address = current_user.wallet_address
    model = await SQLAlchemyOnboardingRepository(session).latest_for_user_or_wallet(
        user_id=current_user.id if current_user else None,
        wallet_address=wallet_address,
    )
    return OnboardingAPIResponse(data=_response_payload(model) if model else None)


@router.get(
    "/responses",
    response_model=OnboardingAPIResponse,
    response_model_by_alias=True,
    summary="List beta onboarding responses",
)
async def list_onboarding_responses(
    page: PageParams = Depends(),
    wallet_address: str | None = Query(default=None, alias="walletAddress"),
    profile: OnboardingProfile | None = Query(default=None),
    blockchain_security_profile: BlockchainSecurityProfile | None = Query(
        default=None,
        alias="blockchainSecurityProfile",
    ),
    preferred_format: PreferredFormat | None = Query(default=None, alias="preferredFormat"),
    security_learning_attempt: SecurityLearningAttempt | None = Query(
        default=None,
        alias="securityLearningAttempt",
    ),
    study_technique: StudyTechnique | None = Query(default=None, alias="studyTechnique"),
    difficult_area: DifficultArea | None = Query(default=None, alias="difficultArea"),
    security_relevance_min: int | None = Query(
        default=None,
        alias="securityRelevanceMin",
        ge=1,
        le=5,
    ),
    security_relevance_max: int | None = Query(
        default=None,
        alias="securityRelevanceMax",
        ge=1,
        le=5,
    ),
    beta_intent: BetaIntent | None = Query(default=None, alias="betaIntent"),
    status: str | None = Query(default=None, max_length=40),
    created_from: datetime | None = Query(default=None, alias="createdFrom"),
    created_to: datetime | None = Query(default=None, alias="createdTo"),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.MODERATOR])),
    session: AsyncSession = Depends(get_db_session),
) -> OnboardingAPIResponse:
    _ = current_user
    responses = await SQLAlchemyOnboardingRepository(session).list(
        limit=page.limit,
        offset=page.offset,
        wallet_address=wallet_address,
        profile=str(profile) if profile else None,
        blockchain_security_profile=(
            str(blockchain_security_profile) if blockchain_security_profile else None
        ),
        preferred_format=str(preferred_format) if preferred_format else None,
        security_learning_attempt=(
            str(security_learning_attempt) if security_learning_attempt else None
        ),
        study_technique=str(study_technique) if study_technique else None,
        difficult_area=str(difficult_area) if difficult_area else None,
        security_relevance_min=security_relevance_min,
        security_relevance_max=security_relevance_max,
        beta_intent=str(beta_intent) if beta_intent else None,
        status=status,
        created_from=created_from,
        created_to=created_to,
    )
    return OnboardingAPIResponse(data=[_response_payload(item) for item in responses])


@router.get(
    "/responses/export.csv",
    summary="Export beta onboarding responses as CSV",
)
async def export_onboarding_responses_csv(
    page: PageParams = Depends(),
    wallet_address: str | None = Query(default=None, alias="walletAddress"),
    profile: OnboardingProfile | None = Query(default=None),
    blockchain_security_profile: BlockchainSecurityProfile | None = Query(
        default=None,
        alias="blockchainSecurityProfile",
    ),
    preferred_format: PreferredFormat | None = Query(default=None, alias="preferredFormat"),
    security_learning_attempt: SecurityLearningAttempt | None = Query(
        default=None,
        alias="securityLearningAttempt",
    ),
    study_technique: StudyTechnique | None = Query(default=None, alias="studyTechnique"),
    difficult_area: DifficultArea | None = Query(default=None, alias="difficultArea"),
    security_relevance_min: int | None = Query(
        default=None,
        alias="securityRelevanceMin",
        ge=1,
        le=5,
    ),
    security_relevance_max: int | None = Query(
        default=None,
        alias="securityRelevanceMax",
        ge=1,
        le=5,
    ),
    beta_intent: BetaIntent | None = Query(default=None, alias="betaIntent"),
    status: str | None = Query(default=None, max_length=40),
    created_from: datetime | None = Query(default=None, alias="createdFrom"),
    created_to: datetime | None = Query(default=None, alias="createdTo"),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.MODERATOR])),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    _ = current_user
    responses = await SQLAlchemyOnboardingRepository(session).list(
        limit=page.limit,
        offset=page.offset,
        wallet_address=wallet_address,
        profile=str(profile) if profile else None,
        blockchain_security_profile=(
            str(blockchain_security_profile) if blockchain_security_profile else None
        ),
        preferred_format=str(preferred_format) if preferred_format else None,
        security_learning_attempt=(
            str(security_learning_attempt) if security_learning_attempt else None
        ),
        study_technique=str(study_technique) if study_technique else None,
        difficult_area=str(difficult_area) if difficult_area else None,
        security_relevance_min=security_relevance_min,
        security_relevance_max=security_relevance_max,
        beta_intent=str(beta_intent) if beta_intent else None,
        status=status,
        created_from=created_from,
        created_to=created_to,
    )
    return _csv_response(responses)
