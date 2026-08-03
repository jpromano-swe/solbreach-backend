from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import Settings, get_settings
from app.core.database.session import get_db_session
from app.core.dependencies.auth import get_current_user
from app.core.dependencies.sandbox import get_sandbox_runtime
from app.modules.analytics.infrastructure.repositories.sqlalchemy_analytics_repository import (
    SQLAlchemyAnalyticsRepository,
)
from app.modules.badges.application.use_cases.badges import EvaluateUserBadgesUseCase
from app.modules.badges.infrastructure.repositories.sqlalchemy_badge_repository import (
    SQLAlchemyBadgeRepository,
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


def _lab_id(data: dict | None = None) -> str | None:
    if not data:
        return None
    return data.get("lab_id") or data.get("labId")


def _action_family(action_type: str) -> str | None:
    normalized = action_type.upper()
    if "DEPOSIT" in normalized:
        return "deposit"
    if "WITHDRAW" in normalized or "BORROW" in normalized:
        return "borrow"
    return None


def _transaction_metadata(data: dict, payload: ResearchLabTransactionRequest) -> dict:
    protocol_state = data.get("protocolState") or data.get("protocol_state") or {}
    parameters = payload.parameters or {}
    return {
        "actionType": payload.action_type,
        "executionStatus": data.get("executionStatus") or data.get("execution_status"),
        "transactionRef": data.get("transactionRef") or data.get("transaction_ref"),
        "amount": parameters.get("amount"),
        "collateralAccountRef": parameters.get("collateral_account_ref"),
        "vaultAccountRef": parameters.get("vault_account_ref"),
        "depositPathType": protocol_state.get("depositPathType"),
        "hasOfficialDeposit": protocol_state.get("hasOfficialDeposit"),
        "hasExploitDeposit": protocol_state.get("hasExploitDeposit"),
        "poolLiquidity": protocol_state.get("poolLiquidity"),
        "creditedCollateral": protocol_state.get("creditedCollateral"),
        "maxBorrow": protocol_state.get("maxBorrow"),
        "availableBorrow": protocol_state.get("availableBorrow"),
        "maxDrainAmount": protocol_state.get("maxDrainAmount"),
        "borrowedTotal": protocol_state.get("borrowedTotal"),
        "maxDrainSatisfied": protocol_state.get("maxDrainSatisfied"),
        "rejectionReason": _rejection_reason(data, protocol_state),
    }


def _rejection_reason(data: dict, protocol_state: dict) -> str | None:
    if protocol_state.get("lastRejectedReason"):
        return protocol_state["lastRejectedReason"]
    for evidence in data.get("userFacingEvidence") or []:
        if evidence.get("severity") in {"error", "warning"}:
            return evidence.get("summary")
    logs = data.get("logs") or []
    return logs[0] if logs else None


async def _record_lab_event(
    analytics: SQLAlchemyAnalyticsRepository,
    *,
    event_type: str,
    current_user: User,
    session_id: str | None = None,
    lab_id: str | None = None,
    subject_type: str = "research_lab_session",
    subject_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    await analytics.record(
        event_type=event_type,
        user_id=current_user.id,
        wallet_address=current_user.wallet_address,
        subject_type=subject_type,
        subject_id=subject_id or session_id or lab_id,
        session_id=session_id,
        lab_id=lab_id,
        metadata=metadata or {},
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
    data = await _service(session, runtime, settings).list_labs()
    await _record_lab_event(
        SQLAlchemyAnalyticsRepository(session),
        event_type="research_labs_catalog_viewed",
        current_user=current_user,
        subject_type="research_lab_catalog",
        subject_id="research_labs",
    )
    await session.commit()
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
    data = await _service(session, runtime, settings).get_lab(lab_id)
    await _record_lab_event(
        SQLAlchemyAnalyticsRepository(session),
        event_type="research_lab_opened",
        current_user=current_user,
        lab_id=lab_id,
        subject_type="research_lab",
        subject_id=lab_id,
    )
    await session.commit()
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
        session_id=data["session_id"],
        lab_id=data["lab_id"],
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
    "/sessions/{session_id}/explorer",
    response_model=ResearchLabAPIResponse,
    summary="Get Research Lab explorer snapshot",
    description=("Returns a session-scoped, learner-safe explorer projection for supported labs."),
)
async def get_research_lab_explorer(
    session_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    runtime: SandboxRuntime = Depends(get_sandbox_runtime),
    settings: Settings = Depends(get_settings),
) -> ResearchLabAPIResponse:
    data = await _service(session, runtime, settings).get_explorer(current_user, session_id)
    await session.commit()
    return ResearchLabAPIResponse(data=data)


@router.get(
    "/sessions/{session_id}/scope",
    response_model=ResearchLabAPIResponse,
    summary="Get Research Lab task scope",
    description="Returns session-owned task/category scope metadata for supported labs.",
)
async def get_research_lab_scope(
    session_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    runtime: SandboxRuntime = Depends(get_sandbox_runtime),
    settings: Settings = Depends(get_settings),
) -> ResearchLabAPIResponse:
    data = await _service(session, runtime, settings).get_scope(current_user, session_id)
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
    analytics = SQLAlchemyAnalyticsRepository(session)
    await analytics.record(
        event_type="account_inspected",
        user_id=current_user.id,
        wallet_address=current_user.wallet_address,
        subject_type="research_lab_session",
        subject_id=session_id,
        session_id=session_id,
        metadata={"account_ref": "list"},
    )
    await _record_lab_event(
        analytics,
        event_type="rl1_account_state_viewed",
        current_user=current_user,
        session_id=session_id,
        metadata={"accountRef": "list"},
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
    analytics = SQLAlchemyAnalyticsRepository(session)
    await analytics.record(
        event_type="account_inspected",
        user_id=current_user.id,
        wallet_address=current_user.wallet_address,
        subject_type="research_lab_session",
        subject_id=session_id,
        session_id=session_id,
        metadata={"account_ref": account_ref},
    )
    await _record_lab_event(
        analytics,
        event_type="rl1_account_state_viewed",
        current_user=current_user,
        session_id=session_id,
        metadata={"accountRef": account_ref},
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
    analytics = SQLAlchemyAnalyticsRepository(session)
    metadata = _transaction_metadata(data, payload)
    execution_status = metadata["executionStatus"]
    action_family = _action_family(payload.action_type)
    await analytics.record(
        event_type="sandbox_transaction_submitted",
        user_id=current_user.id,
        wallet_address=current_user.wallet_address,
        subject_type="research_lab_session",
        subject_id=session_id,
        session_id=session_id,
        metadata=metadata,
    )
    await _record_lab_event(
        analytics,
        event_type="rl1_transaction_submitted",
        current_user=current_user,
        session_id=session_id,
        metadata=metadata,
    )
    if action_family is not None:
        await _record_lab_event(
            analytics,
            event_type=f"rl1_{action_family}_submitted",
            current_user=current_user,
            session_id=session_id,
            metadata=metadata,
        )
        await _record_lab_event(
            analytics,
            event_type=(
                f"rl1_{action_family}_accepted"
                if execution_status == "success"
                else f"rl1_{action_family}_rejected"
            ),
            current_user=current_user,
            session_id=session_id,
            metadata=metadata,
        )
    if metadata.get("maxDrainSatisfied"):
        await _record_lab_event(
            analytics,
            event_type="rl1_max_drain_used",
            current_user=current_user,
            session_id=session_id,
            metadata=metadata,
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
    analytics = SQLAlchemyAnalyticsRepository(session)
    await analytics.record(
        event_type="objective_verification_requested",
        user_id=current_user.id,
        wallet_address=current_user.wallet_address,
        subject_type="research_lab_session",
        subject_id=session_id,
        session_id=session_id,
        metadata={},
    )
    await _record_lab_event(
        analytics,
        event_type="rl1_impact_verification_requested",
        current_user=current_user,
        session_id=session_id,
        metadata={"objectiveRef": payload.objective_ref if payload else None},
    )
    data = await _service(session, runtime, settings).verify_objective(
        current_user, session_id, payload.objective_ref if payload else None
    )
    if data["passed"]:
        await analytics.record(
            event_type="research_exploit_validated",
            user_id=current_user.id,
            wallet_address=current_user.wallet_address,
            subject_type="research_lab_session",
            subject_id=session_id,
            session_id=session_id,
            metadata={"objective_ref": data["objective_ref"]},
        )
        await analytics.record(
            event_type="report_unlocked",
            user_id=current_user.id,
            wallet_address=current_user.wallet_address,
            subject_type="research_lab_session",
            subject_id=session_id,
            session_id=session_id,
            metadata={},
        )
        await _record_lab_event(
            analytics,
            event_type="rl1_impact_verified",
            current_user=current_user,
            session_id=session_id,
            metadata={"objectiveRef": data["objective_ref"]},
        )
        await _record_lab_event(
            analytics,
            event_type="rl1_report_finding_unlocked",
            current_user=current_user,
            session_id=session_id,
            metadata={"objectiveRef": data["objective_ref"]},
        )
    else:
        await _record_lab_event(
            analytics,
            event_type="rl1_impact_rejected",
            current_user=current_user,
            session_id=session_id,
            metadata={
                "objectiveRef": data.get("objective_ref") or data.get("objectiveRef"),
                "failureReason": data.get("failure_reason") or data.get("failureReason"),
            },
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
    if data.get("status") != "locked":
        await _record_lab_event(
            SQLAlchemyAnalyticsRepository(session),
            event_type="rl1_finding_review_started",
            current_user=current_user,
            session_id=session_id,
            metadata={"status": data.get("status")},
        )
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
    analytics = SQLAlchemyAnalyticsRepository(session)
    review_metadata = {
        "score": data["score"],
        "attempts": data["findingReviewAttempts"],
        "failedQuestionIds": data["failedQuestionIds"],
    }
    await analytics.record(
        event_type=(
            "finding_review_passed" if data["findingReviewPassed"] else "finding_review_retry"
        ),
        user_id=current_user.id,
        wallet_address=current_user.wallet_address,
        subject_type="research_lab_session",
        subject_id=session_id,
        session_id=session_id,
        metadata=review_metadata,
    )
    await _record_lab_event(
        analytics,
        event_type="rl1_finding_review_submitted",
        current_user=current_user,
        session_id=session_id,
        metadata=review_metadata,
    )
    await _record_lab_event(
        analytics,
        event_type=(
            "rl1_finding_review_passed"
            if data["findingReviewPassed"]
            else "rl1_finding_review_failed"
        ),
        current_user=current_user,
        session_id=session_id,
        metadata=review_metadata,
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
    if data.get("status") != "locked":
        await _record_lab_event(
            SQLAlchemyAnalyticsRepository(session),
            event_type="rl1_audit_report_opened",
            current_user=current_user,
            session_id=session_id,
            metadata={"status": data.get("status")},
        )
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
    analytics = SQLAlchemyAnalyticsRepository(session)
    await analytics.record(
        event_type="report_started",
        user_id=current_user.id,
        wallet_address=current_user.wallet_address,
        subject_type="research_lab_session",
        subject_id=session_id,
        session_id=session_id,
        metadata={"status": data["status"]},
    )
    await _record_lab_event(
        analytics,
        event_type="rl1_audit_report_saved",
        current_user=current_user,
        session_id=session_id,
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
    analytics = SQLAlchemyAnalyticsRepository(session)
    if data["lab_completed"]:
        lab_session = await SQLAlchemyResearchLabRepository(session).get_session(session_id)
        await EvaluateUserBadgesUseCase(
            SQLAlchemyBadgeRepository(session),
            analytics,
        ).earn_for_research_lab_completion(
            current_user,
            lab_session.lab_id if lab_session is not None else "",
        )
    report_metadata = {"status": data["status"], "labCompleted": data["lab_completed"]}
    await analytics.record(
        event_type="report_submitted",
        user_id=current_user.id,
        wallet_address=current_user.wallet_address,
        subject_type="research_lab_session",
        subject_id=session_id,
        session_id=session_id,
        metadata=report_metadata,
    )
    await analytics.record(
        event_type=(
            "research_lab_completed" if data["lab_completed"] else "research_lab_report_retry"
        ),
        user_id=current_user.id,
        wallet_address=current_user.wallet_address,
        subject_type="research_lab_session",
        subject_id=session_id,
        session_id=session_id,
        metadata={
            "status": data["status"],
            "xp_awarded": data["xp_awarded"],
        },
    )
    await _record_lab_event(
        analytics,
        event_type="rl1_audit_report_submitted",
        current_user=current_user,
        session_id=session_id,
        metadata=report_metadata,
    )
    await _record_lab_event(
        analytics,
        event_type=(
            "rl1_audit_report_accepted" if data["lab_completed"] else "rl1_audit_report_rejected"
        ),
        current_user=current_user,
        session_id=session_id,
        metadata={
            "status": data["status"],
            "xpAwarded": data["xp_awarded"],
            "labCompleted": data["lab_completed"],
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
