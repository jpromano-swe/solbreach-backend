from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db_session
from app.core.dependencies.auth import get_current_user, require_roles
from app.core.dependencies.blockchain import get_blockchain_client
from app.modules.analytics.infrastructure.repositories.sqlalchemy_analytics_repository import (
    SQLAlchemyAnalyticsRepository,
)
from app.modules.badges.application.use_cases.badges import EvaluateUserBadgesUseCase
from app.modules.badges.infrastructure.repositories.sqlalchemy_badge_repository import (
    SQLAlchemyBadgeRepository,
)
from app.modules.certifications.infrastructure.repositories import (
    sqlalchemy_certification_repository,
)
from app.modules.certifications.presentation.schemas.certification import CertificationResponse
from app.modules.levels.application.use_cases.create_level import CreateLevelUseCase
from app.modules.levels.application.use_cases.get_level import GetLevelUseCase
from app.modules.levels.application.use_cases.get_level_status import GetLevelStatusUseCase
from app.modules.levels.application.use_cases.list_levels import ListLevelsUseCase
from app.modules.levels.application.use_cases.setup_level import SetupLevelUseCase
from app.modules.levels.application.use_cases.start_level import StartLevelUseCase
from app.modules.levels.application.use_cases.submit_level import SubmitLevelUseCase
from app.modules.levels.domain.entities.level import Level
from app.modules.levels.domain.entities.level_session import LevelSession
from app.modules.levels.domain.services.level_access import LevelAccessService
from app.modules.levels.infrastructure.repositories.sqlalchemy_level_repository import (
    SQLAlchemyLevelRepository,
)
from app.modules.levels.infrastructure.repositories.sqlalchemy_level_session_repository import (
    SQLAlchemyLevelSessionRepository,
)
from app.modules.levels.presentation.schemas.level import (
    LevelCreateRequest,
    LevelExecutionMetadata,
    LevelResponse,
    LevelSessionResponse,
    LevelSetupRequest,
    LevelSetupResponse,
    LevelStartResponse,
    LevelStatusResponse,
    LevelSubmitErrorData,
    LevelSubmitRequest,
    LevelSubmitResponse,
    LevelSubmitSuccessData,
)
from app.modules.progress.infrastructure.repositories.sqlalchemy_progress_repository import (
    SQLAlchemyProgressRepository,
)
from app.modules.progress.presentation.schemas.progress import ProgressResponse
from app.modules.submissions.domain.services.verification_engine import VerificationEngine
from app.modules.submissions.infrastructure.repositories.sqlalchemy_submission_repository import (
    SQLAlchemySubmissionRepository,
)
from app.modules.submissions.presentation.schemas.submission import SubmissionResponse
from app.modules.users.domain.entities.user import User, UserRole
from app.modules.users.infrastructure.repositories.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
)
from app.shared.blockchain import BlockchainClientInterface
from app.shared.events.event_bus import InMemoryEventPublisher
from app.shared.schemas.pagination import PageParams

router = APIRouter()

AUTH_ERROR_EXAMPLE = {
    "error": {
        "code": "UNAUTHORIZED",
        "message": "Missing bearer token",
    }
}

LEVEL_LOCKED_EXAMPLE = {
    "error": {
        "code": "LEVEL_LOCKED",
        "message": "Complete the previous level before starting this one",
    }
}

LEVEL_NOT_STARTED_EXAMPLE = {
    "error": {
        "code": "LEVEL_NOT_STARTED",
        "message": "Start the level before setup",
    }
}

INVALID_SUBMISSION_EXAMPLE = {
    "error": {
        "code": "INVALID_SUBMISSION",
        "message": "Transaction signature was already submitted",
    }
}


def _level_response(level: Level) -> LevelResponse:
    return LevelResponse.model_validate(level, from_attributes=True)


def _session_response(session: LevelSession) -> LevelSessionResponse:
    return LevelSessionResponse.model_validate(session, from_attributes=True)


def _execution_metadata(level: Level) -> LevelExecutionMetadata | None:
    execution = level.deployment_info.get("execution") or {}
    if execution.get("enabled") is not True:
        return None
    return LevelExecutionMetadata(
        setup_required=True,
        network=str(execution.get("network", "devnet")),
        setup_endpoint=f"/api/v1/levels/{level.id}/setup",
        submit_proof_fields=["transaction_signature", "wallet_address", "level_session_id"],
        execution_mode=str(execution.get("mode", "wallet_signed_demo_transaction")),
    )


@router.get(
    "",
    response_model=list[LevelResponse],
    summary="List active vulnerability levels",
    description="Returns the active vulnerability level catalog ordered for sequential gameplay.",
)
async def list_levels(
    page: PageParams = Depends(),
    session: AsyncSession = Depends(get_db_session),
) -> list[LevelResponse]:
    levels = await ListLevelsUseCase(SQLAlchemyLevelRepository(session)).execute(
        page.limit, page.offset
    )
    return [_level_response(level) for level in levels]


@router.get(
    "/{level_id}",
    response_model=LevelResponse,
    summary="Get level metadata",
    description="Returns level instructions, resources, XP reward, and verification requirements.",
)
async def get_level(
    level_id: str, session: AsyncSession = Depends(get_db_session)
) -> LevelResponse:
    return _level_response(
        await GetLevelUseCase(SQLAlchemyLevelRepository(session)).execute(level_id)
    )


@router.post(
    "",
    response_model=LevelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a level",
    description=(
        "Admin/moderator endpoint for creating vulnerability levels and verification configs."
    ),
)
async def create_level(
    payload: LevelCreateRequest,
    _: User = Depends(require_roles([UserRole.ADMIN, UserRole.MODERATOR])),
    session: AsyncSession = Depends(get_db_session),
) -> LevelResponse:
    level = await CreateLevelUseCase(SQLAlchemyLevelRepository(session)).execute(
        slug=payload.slug,
        title=payload.title,
        description=payload.description,
        order=payload.order,
        stage=payload.stage,
        vulnerability_id=payload.vulnerability_id,
        vulnerability_category=payload.vulnerability_category,
        difficulty=payload.difficulty,
        objectives=payload.objectives,
        instructions=payload.instructions,
        verification_requirements=payload.verification_requirements,
        repository_url=payload.repository_url,
        resources=payload.resources,
        verification_config=payload.verification_config,
        deployment_info=payload.deployment_info,
        xp_reward=payload.xp_reward,
    )
    await session.commit()
    return _level_response(level)


@router.post(
    "/{level_id}/start",
    response_model=LevelStartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start or resume a level",
    description=(
        "Creates or resumes a gameplay session for the authenticated user. "
        "For executable levels, the response includes frontend execution metadata "
        "such as devnet network, setup endpoint, and proof fields."
    ),
    responses={
        401: {
            "description": "Missing or invalid bearer token",
            "content": {"application/json": {"example": AUTH_ERROR_EXAMPLE}},
        },
        403: {
            "description": "Level is locked by sequential progression",
            "content": {"application/json": {"example": LEVEL_LOCKED_EXAMPLE}},
        },
    },
)
async def start_level(
    level_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> LevelStartResponse:
    levels = SQLAlchemyLevelRepository(session)
    progress = SQLAlchemyProgressRepository(session)
    result = await StartLevelUseCase(
        levels,
        SQLAlchemyLevelSessionRepository(session),
        LevelAccessService(levels, progress),
        InMemoryEventPublisher(),
    ).execute(current_user.id, level_id)
    await session.commit()
    await SQLAlchemyAnalyticsRepository(session).record(
        event_type="level_started",
        user_id=current_user.id,
        wallet_address=current_user.wallet_address,
        subject_type="level",
        subject_id=level_id,
        metadata={"session_id": result.session.id, "level_slug": result.level.slug},
    )
    await session.commit()
    return LevelStartResponse(
        level=_level_response(result.level),
        state=result.state.value,
        session=_session_response(result.session),
        execution=_execution_metadata(result.level),
    )


@router.post(
    "/{level_id}/setup",
    response_model=LevelSetupResponse,
    summary="Prepare executable level exploit setup",
    description=(
        "Binds the active level session to the player's wallet and returns deterministic "
        "devnet challenge accounts. The backend does not sign or submit transactions."
    ),
    responses={
        401: {
            "description": "Missing or invalid bearer token",
            "content": {"application/json": {"example": AUTH_ERROR_EXAMPLE}},
        },
        409: {
            "description": "Level has not been started or session is bound to another wallet",
            "content": {"application/json": {"example": LEVEL_NOT_STARTED_EXAMPLE}},
        },
    },
)
async def setup_level(
    level_id: str,
    payload: LevelSetupRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> LevelSetupResponse:
    levels = SQLAlchemyLevelRepository(session)
    progress = SQLAlchemyProgressRepository(session)
    result = await SetupLevelUseCase(
        levels,
        SQLAlchemyLevelSessionRepository(session),
        LevelAccessService(levels, progress),
    ).execute(current_user, level_id, payload.wallet_address)
    await SQLAlchemyAnalyticsRepository(session).record(
        event_type="level_setup_ready",
        user_id=current_user.id,
        wallet_address=payload.wallet_address,
        subject_type="level",
        subject_id=level_id,
        metadata={"session_id": result.session.id, "level_slug": result.level.slug},
    )
    await session.commit()
    return LevelSetupResponse(
        level_id=result.level.id,
        level_session_id=result.session.id,
        exploit_status=result.exploit_status,
        challenge=result.challenge,
    )


@router.get(
    "/{level_id}/status",
    response_model=LevelStatusResponse,
    summary="Get current level state",
    description=(
        "Returns the current gameplay and exploit state for this user, including "
        "submission history, XP earned, unlock status, and session-bound challenge context."
    ),
    responses={
        401: {
            "description": "Missing or invalid bearer token",
            "content": {"application/json": {"example": AUTH_ERROR_EXAMPLE}},
        }
    },
)
async def get_level_status(
    level_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> LevelStatusResponse:
    levels = SQLAlchemyLevelRepository(session)
    progress = SQLAlchemyProgressRepository(session)
    result = await GetLevelStatusUseCase(
        levels,
        SQLAlchemyLevelSessionRepository(session),
        SQLAlchemySubmissionRepository(session),
        LevelAccessService(levels, progress),
    ).execute(current_user.id, level_id)
    progress_response = (
        ProgressResponse.model_validate(result.progress, from_attributes=True)
        if result.progress
        else None
    )
    return LevelStatusResponse(
        level=_level_response(result.level),
        state=result.state.value,
        unlock_status="unlocked" if result.state.value != "locked" else "locked",
        available=result.state.value in {"available", "in_progress", "failed", "completed"},
        session=_session_response(result.session) if result.session else None,
        completed=result.progress is not None,
        progress=progress_response,
        submissions=[
            SubmissionResponse.model_validate(submission, from_attributes=True)
            for submission in result.submissions
        ],
        xp_awarded=result.progress.xp_awarded if result.progress else 0,
        xp_earned=result.progress.xp_awarded if result.progress else 0,
        next_level_id=result.next_level_id,
        exploit_status=result.session.exploit_status.value if result.session else None,
        challenge_context=result.session.challenge_context if result.session else {},
    )


@router.post(
    "/{level_id}/submit",
    response_model=LevelSubmitResponse,
    summary="Submit deterministic exploit proof",
    description=(
        "Verifies a wallet-signed devnet transaction. The backend fetches the "
        "transaction by signature, checks session and wallet binding, prevents replay, "
        "validates required challenge accounts, then updates progression."
    ),
    responses={
        401: {
            "description": "Missing or invalid bearer token",
            "content": {"application/json": {"example": AUTH_ERROR_EXAMPLE}},
        },
        403: {
            "description": "Invalid submission, locked level, or reused transaction signature",
            "content": {
                "application/json": {
                    "example": INVALID_SUBMISSION_EXAMPLE
                }
            },
        },
        409: {
            "description": "Level not started or setup required",
            "content": {"application/json": {"example": LEVEL_NOT_STARTED_EXAMPLE}},
        },
    },
)
async def submit_level(
    level_id: str,
    payload: LevelSubmitRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    blockchain: BlockchainClientInterface = Depends(get_blockchain_client),
) -> LevelSubmitResponse:
    levels = SQLAlchemyLevelRepository(session)
    progress = SQLAlchemyProgressRepository(session)
    result = await SubmitLevelUseCase(
        levels=levels,
        sessions=SQLAlchemyLevelSessionRepository(session),
        submissions=SQLAlchemySubmissionRepository(session),
        progress=progress,
        users=SQLAlchemyUserRepository(session),
        certifications=(
            sqlalchemy_certification_repository.SQLAlchemyCertificationRepository(session)
        ),
        access=LevelAccessService(levels, progress),
        verification=VerificationEngine(),
        events=InMemoryEventPublisher(),
        blockchain=blockchain,
    ).execute(current_user.id, level_id, payload.to_proof())
    analytics = SQLAlchemyAnalyticsRepository(session)
    if result.progress is not None:
        await EvaluateUserBadgesUseCase(
            SQLAlchemyBadgeRepository(session),
            analytics,
        ).earn_for_completed_level(current_user, result.level.order)
    await SQLAlchemyAnalyticsRepository(session).record(
        event_type=(
            "level_submission_verified"
            if result.submission.status.value == "verified"
            else "level_submission_rejected"
        ),
        user_id=current_user.id,
        wallet_address=result.submission.wallet_address,
        subject_type="level",
        subject_id=level_id,
        metadata={
            "session_id": result.session.id,
            "submission_id": result.submission.id,
            "level_slug": result.level.slug,
        },
    )
    await session.commit()
    submission = SubmissionResponse.model_validate(result.submission, from_attributes=True)
    if result.submission.status.value == "rejected":
        return LevelSubmitResponse(
            success=False,
            error=LevelSubmitErrorData(
                code="INVALID_SUBMISSION",
                message="Verification failed",
                details=result.submission.verification_result,
            ),
        )

    return LevelSubmitResponse(
        success=True,
        data=LevelSubmitSuccessData(
            submission_status=result.submission.status.value.upper(),
            level_completed=result.progress is not None,
            xp_awarded=result.progress.xp_awarded if result.progress else 0,
            next_level_unlocked=result.unlocked_next_level_id is not None,
            unlocked_level_id=result.unlocked_next_level_id,
            submission=submission,
            progress=(
                ProgressResponse.model_validate(result.progress, from_attributes=True)
                if result.progress
                else None
            ),
            certification=(
                CertificationResponse.model_validate(result.certification, from_attributes=True)
                if result.certification
                else None
            ),
        ),
    )
