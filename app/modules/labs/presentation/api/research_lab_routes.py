from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import Settings, get_settings
from app.core.database.session import get_db_session
from app.core.dependencies.auth import get_current_user
from app.core.dependencies.sandbox import get_sandbox_runtime
from app.modules.analytics.infrastructure.repositories.sqlalchemy_analytics_repository import (
    SQLAlchemyAnalyticsRepository,
)
from app.modules.labs.application.use_cases.research_labs import ResearchLabService
from app.modules.labs.infrastructure.repositories.sqlalchemy_research_lab_repository import (
    SQLAlchemyResearchLabRepository,
)
from app.modules.labs.presentation.schemas.research_lab import (
    ResearchLabAPIResponse,
    ResearchLabFindingReviewSubmitRequest,
    ResearchLabPatchFilesRequest,
    ResearchLabReportSaveRequest,
    ResearchLabTransactionRequest,
    ResearchLabVerifyObjectiveRequest,
)
from app.modules.sandbox.domain.runtime import SandboxRuntime
from app.modules.users.domain.entities.user import User
from app.modules.users.infrastructure.repositories.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
)

router = APIRouter()


def _service(
    session: AsyncSession,
    runtime: SandboxRuntime,
    settings: Settings,
) -> ResearchLabService:
    return ResearchLabService(
        SQLAlchemyResearchLabRepository(session),
        SQLAlchemyUserRepository(session),
        runtime,
        settings,
    )


@router.get(
    "",
    response_model=ResearchLabAPIResponse,
    summary="List Research Labs",
    description="Returns learner-safe Research Lab catalog metadata.",
)
async def list_research_labs(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    runtime: SandboxRuntime = Depends(get_sandbox_runtime),
    settings: Settings = Depends(get_settings),
) -> ResearchLabAPIResponse:
    _ = current_user
    data = await _service(session, runtime, settings).list_labs()
    return ResearchLabAPIResponse(data=data)


@router.get(
    "/{lab_id}",
    response_model=ResearchLabAPIResponse,
    summary="Get Research Lab metadata",
    description="Returns learner-safe manifest details for one Research Lab.",
)
async def get_research_lab(
    lab_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    runtime: SandboxRuntime = Depends(get_sandbox_runtime),
    settings: Settings = Depends(get_settings),
) -> ResearchLabAPIResponse:
    _ = current_user
    data = await _service(session, runtime, settings).get_lab(lab_id)
    return ResearchLabAPIResponse(data=data)


@router.post(
    "/{lab_id}/sessions",
    response_model=ResearchLabAPIResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Research Lab session",
    description=(
        "Hydrates the lab template in a backend sandbox and returns only learner-visible "
        "files and terminal events."
    ),
)
async def create_research_lab_session(
    lab_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    runtime: SandboxRuntime = Depends(get_sandbox_runtime),
    settings: Settings = Depends(get_settings),
) -> ResearchLabAPIResponse:
    data = await _service(session, runtime, settings).create_session(current_user, lab_id)
    await SQLAlchemyAnalyticsRepository(session).record(
        event_type="research_lab_session_started",
        user_id=current_user.id,
        wallet_address=current_user.wallet_address,
        subject_type="research_lab",
        subject_id=data["lab_id"],
        metadata={"session_id": data["session_id"], "lab_slug": data["lab_slug"]},
    )
    await session.commit()
    return ResearchLabAPIResponse(data=data)


@router.get(
    "/sessions/{session_id}",
    response_model=ResearchLabAPIResponse,
    summary="Get Research Lab session",
    description="Returns current session state, allowed files, terminal events, and test status.",
)
async def get_research_lab_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    runtime: SandboxRuntime = Depends(get_sandbox_runtime),
    settings: Settings = Depends(get_settings),
) -> ResearchLabAPIResponse:
    data = await _service(session, runtime, settings).get_session(current_user, session_id)
    await session.commit()
    return ResearchLabAPIResponse(data=data)


@router.patch(
    "/sessions/{session_id}/files",
    response_model=ResearchLabAPIResponse,
    summary="Patch allowed Research Lab files",
    description="Stores edits for allowed files only and applies them inside the sandbox.",
)
async def patch_research_lab_files(
    session_id: str,
    payload: ResearchLabPatchFilesRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    runtime: SandboxRuntime = Depends(get_sandbox_runtime),
    settings: Settings = Depends(get_settings),
) -> ResearchLabAPIResponse:
    data = await _service(session, runtime, settings).patch_files(
        current_user,
        session_id,
        [file.model_dump() for file in payload.files],
    )
    await session.commit()
    return ResearchLabAPIResponse(data=data)


@router.get(
    "/sessions/{session_id}/accounts",
    response_model=ResearchLabAPIResponse,
    summary="List visible Research Lab accounts",
    description="Returns learner-visible sandbox account summaries for inspection.",
)
async def list_research_lab_accounts(
    session_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    runtime: SandboxRuntime = Depends(get_sandbox_runtime),
    settings: Settings = Depends(get_settings),
) -> ResearchLabAPIResponse:
    data = await _service(session, runtime, settings).list_accounts(current_user, session_id)
    await SQLAlchemyAnalyticsRepository(session).record(
        event_type="account_inspected",
        user_id=current_user.id,
        wallet_address=current_user.wallet_address,
        subject_type="research_lab_session",
        subject_id=session_id,
        metadata={"account_ref": "list"},
    )
    await session.commit()
    return ResearchLabAPIResponse(data=data)


@router.get(
    "/sessions/{session_id}/accounts/{account_ref}",
    response_model=ResearchLabAPIResponse,
    summary="Get visible Research Lab account state",
    description="Returns one learner-visible sandbox account snapshot.",
)
async def get_research_lab_account(
    session_id: str,
    account_ref: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    runtime: SandboxRuntime = Depends(get_sandbox_runtime),
    settings: Settings = Depends(get_settings),
) -> ResearchLabAPIResponse:
    data = await _service(session, runtime, settings).get_account(
        current_user, session_id, account_ref
    )
    await SQLAlchemyAnalyticsRepository(session).record(
        event_type="account_inspected",
        user_id=current_user.id,
        wallet_address=current_user.wallet_address,
        subject_type="research_lab_session",
        subject_id=session_id,
        metadata={"account_ref": account_ref},
    )
    await session.commit()
    return ResearchLabAPIResponse(data=data)


@router.post(
    "/sessions/{session_id}/transactions",
    response_model=ResearchLabAPIResponse,
    summary="Submit Research Lab sandbox transaction",
    description="Executes a supported exploit action inside the assigned sandbox session.",
)
async def submit_research_lab_transaction(
    session_id: str,
    payload: ResearchLabTransactionRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    runtime: SandboxRuntime = Depends(get_sandbox_runtime),
    settings: Settings = Depends(get_settings),
) -> ResearchLabAPIResponse:
    data = await _service(session, runtime, settings).submit_transaction(
        current_user, session_id, payload.action_type, payload.parameters
    )
    await SQLAlchemyAnalyticsRepository(session).record(
        event_type="sandbox_transaction_submitted",
        user_id=current_user.id,
        wallet_address=current_user.wallet_address,
        subject_type="research_lab_session",
        subject_id=session_id,
        metadata={
            "action_type": payload.action_type,
            "result": data["execution_status"],
            "transaction_ref": data["transaction_ref"],
        },
    )
    await session.commit()
    return ResearchLabAPIResponse(data=data)


@router.get(
    "/sessions/{session_id}/transactions",
    response_model=ResearchLabAPIResponse,
    summary="List Research Lab sandbox transactions",
    description="Returns transaction summaries stored for this learner-owned session.",
)
async def list_research_lab_transactions(
    session_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    runtime: SandboxRuntime = Depends(get_sandbox_runtime),
    settings: Settings = Depends(get_settings),
) -> ResearchLabAPIResponse:
    data = await _service(session, runtime, settings).list_transactions(current_user, session_id)
    await session.commit()
    return ResearchLabAPIResponse(data=data)


@router.get(
    "/sessions/{session_id}/transactions/{transaction_ref}/logs",
    response_model=ResearchLabAPIResponse,
    summary="Get Research Lab transaction logs",
    description="Returns learner-safe logs for a sandbox transaction.",
)
async def get_research_lab_transaction_logs(
    session_id: str,
    transaction_ref: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    runtime: SandboxRuntime = Depends(get_sandbox_runtime),
    settings: Settings = Depends(get_settings),
) -> ResearchLabAPIResponse:
    data = await _service(session, runtime, settings).transaction_logs(
        current_user, session_id, transaction_ref
    )
    await SQLAlchemyAnalyticsRepository(session).record(
        event_type="transaction_logs_viewed",
        user_id=current_user.id,
        wallet_address=current_user.wallet_address,
        subject_type="research_lab_session",
        subject_id=session_id,
        metadata={"transaction_ref": transaction_ref},
    )
    await session.commit()
    return ResearchLabAPIResponse(data=data)


@router.post(
    "/sessions/{session_id}/verify-objective",
    response_model=ResearchLabAPIResponse,
    summary="Verify Research Lab objective",
    description="Checks objective predicates against sandbox runtime state.",
)
async def verify_research_lab_objective(
    session_id: str,
    payload: ResearchLabVerifyObjectiveRequest | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    runtime: SandboxRuntime = Depends(get_sandbox_runtime),
    settings: Settings = Depends(get_settings),
) -> ResearchLabAPIResponse:
    await SQLAlchemyAnalyticsRepository(session).record(
        event_type="objective_verification_requested",
        user_id=current_user.id,
        wallet_address=current_user.wallet_address,
        subject_type="research_lab_session",
        subject_id=session_id,
        metadata={},
    )
    data = await _service(session, runtime, settings).verify_objective(
        current_user, session_id, payload.objective_ref if payload else None
    )
    if data["passed"]:
        await SQLAlchemyAnalyticsRepository(session).record(
            event_type="research_exploit_validated",
            user_id=current_user.id,
            wallet_address=current_user.wallet_address,
            subject_type="research_lab_session",
            subject_id=session_id,
            metadata={"objective_ref": data["objective_ref"]},
        )
        await SQLAlchemyAnalyticsRepository(session).record(
            event_type="report_unlocked",
            user_id=current_user.id,
            wallet_address=current_user.wallet_address,
            subject_type="research_lab_session",
            subject_id=session_id,
            metadata={},
        )
    await session.commit()
    return ResearchLabAPIResponse(data=data)


@router.post(
    "/sessions/{session_id}/run-tests",
    response_model=ResearchLabAPIResponse,
    summary="Run Research Lab tests",
    description="Runs only the predefined backend-owned test command for this lab session.",
)
async def run_research_lab_tests(
    session_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    runtime: SandboxRuntime = Depends(get_sandbox_runtime),
    settings: Settings = Depends(get_settings),
) -> ResearchLabAPIResponse:
    data = await _service(session, runtime, settings).run_tests(current_user, session_id)
    await SQLAlchemyAnalyticsRepository(session).record(
        event_type=(
            "research_lab_report_unlocked"
            if data["status"] == "passed"
            else "research_lab_tests_failed"
        ),
        user_id=current_user.id,
        wallet_address=current_user.wallet_address,
        subject_type="research_lab_session",
        subject_id=session_id,
        metadata={
            "test_run_id": data["test_run_id"],
            "status": data["status"],
            "xp_awarded": data["xp_awarded"],
        },
    )
    await session.commit()
    return ResearchLabAPIResponse(data=data)


@router.get(
    "/sessions/{session_id}/finding-review",
    response_model=ResearchLabAPIResponse,
    summary="Get Research Lab finding review",
    description="Returns deterministic backend-owned finding review state for this RL1 session.",
)
async def get_research_lab_finding_review(
    session_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    runtime: SandboxRuntime = Depends(get_sandbox_runtime),
    settings: Settings = Depends(get_settings),
) -> ResearchLabAPIResponse:
    data = await _service(session, runtime, settings).get_finding_review(current_user, session_id)
    await session.commit()
    return ResearchLabAPIResponse(data=data)


@router.post(
    "/sessions/{session_id}/finding-review/submit",
    response_model=ResearchLabAPIResponse,
    summary="Submit Research Lab finding review",
    description="Grades deterministic RL1 finding-review answers and persists backend-owned state.",
)
async def submit_research_lab_finding_review(
    session_id: str,
    payload: ResearchLabFindingReviewSubmitRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    runtime: SandboxRuntime = Depends(get_sandbox_runtime),
    settings: Settings = Depends(get_settings),
) -> ResearchLabAPIResponse:
    data = await _service(session, runtime, settings).submit_finding_review(
        current_user, session_id, payload.answers
    )
    await SQLAlchemyAnalyticsRepository(session).record(
        event_type=(
            "finding_review_passed"
            if data["findingReviewPassed"]
            else "finding_review_retry"
        ),
        user_id=current_user.id,
        wallet_address=current_user.wallet_address,
        subject_type="research_lab_session",
        subject_id=session_id,
        metadata={
            "score": data["score"],
            "attempts": data["findingReviewAttempts"],
            "failed_question_ids": data["failedQuestionIds"],
        },
    )
    await session.commit()
    return ResearchLabAPIResponse(data=data)


@router.get(
    "/sessions/{session_id}/report",
    response_model=ResearchLabAPIResponse,
    summary="Get Research Lab report",
    description="Returns locked, draft, retry, or accepted report state for a lab session.",
)
async def get_research_lab_report(
    session_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    runtime: SandboxRuntime = Depends(get_sandbox_runtime),
    settings: Settings = Depends(get_settings),
) -> ResearchLabAPIResponse:
    data = await _service(session, runtime, settings).get_report(current_user, session_id)
    await session.commit()
    return ResearchLabAPIResponse(data=data)


@router.put(
    "/sessions/{session_id}/report",
    response_model=ResearchLabAPIResponse,
    summary="Save Research Lab report draft",
    description="Saves structured report fields after backend impact verification unlocks the report.",
)
async def save_research_lab_report(
    session_id: str,
    payload: ResearchLabReportSaveRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    runtime: SandboxRuntime = Depends(get_sandbox_runtime),
    settings: Settings = Depends(get_settings),
) -> ResearchLabAPIResponse:
    data = await _service(session, runtime, settings).save_report_draft(
        current_user,
        session_id,
        payload.fields.model_dump(),
    )
    await SQLAlchemyAnalyticsRepository(session).record(
        event_type="report_started",
        user_id=current_user.id,
        wallet_address=current_user.wallet_address,
        subject_type="research_lab_session",
        subject_id=session_id,
        metadata={"status": data["status"]},
    )
    await session.commit()
    return ResearchLabAPIResponse(data=data)


@router.post(
    "/sessions/{session_id}/report/submit",
    response_model=ResearchLabAPIResponse,
    summary="Submit Research Lab report",
    description="Deterministically validates report understanding and awards XP if accepted.",
)
async def submit_research_lab_report(
    session_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    runtime: SandboxRuntime = Depends(get_sandbox_runtime),
    settings: Settings = Depends(get_settings),
) -> ResearchLabAPIResponse:
    data = await _service(session, runtime, settings).submit_report(current_user, session_id)
    await SQLAlchemyAnalyticsRepository(session).record(
        event_type="report_submitted",
        user_id=current_user.id,
        wallet_address=current_user.wallet_address,
        subject_type="research_lab_session",
        subject_id=session_id,
        metadata={"status": data["status"], "lab_completed": data["lab_completed"]},
    )
    await SQLAlchemyAnalyticsRepository(session).record(
        event_type=(
            "research_lab_completed"
            if data["lab_completed"]
            else "research_lab_report_retry"
        ),
        user_id=current_user.id,
        wallet_address=current_user.wallet_address,
        subject_type="research_lab_session",
        subject_id=session_id,
        metadata={
            "status": data["status"],
            "xp_awarded": data["xp_awarded"],
        },
    )
    await session.commit()
    return ResearchLabAPIResponse(data=data)


@router.get(
    "/sessions/{session_id}/terminal",
    response_model=ResearchLabAPIResponse,
    summary="Poll Research Lab terminal events",
    description="Returns terminal events after the supplied sequence number.",
)
async def get_research_lab_terminal(
    session_id: str,
    after_sequence: int | None = Query(default=None, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    runtime: SandboxRuntime = Depends(get_sandbox_runtime),
    settings: Settings = Depends(get_settings),
) -> ResearchLabAPIResponse:
    data = await _service(session, runtime, settings).terminal_events(
        current_user, session_id, after_sequence
    )
    await session.commit()
    return ResearchLabAPIResponse(data=data)


@router.post(
    "/sessions/{session_id}/reset",
    response_model=ResearchLabAPIResponse,
    summary="Reset Research Lab session",
    description="Restores the initial template and clears test/terminal runtime state.",
)
async def reset_research_lab_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    runtime: SandboxRuntime = Depends(get_sandbox_runtime),
    settings: Settings = Depends(get_settings),
) -> ResearchLabAPIResponse:
    data = await _service(session, runtime, settings).reset_session(current_user, session_id)
    await session.commit()
    return ResearchLabAPIResponse(data=data)
