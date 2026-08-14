from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import Settings, get_settings
from app.core.database.session import get_db_session
from app.core.dependencies.auth import get_current_user
from app.core.exceptions.domain import NotFoundError
from app.modules.breach_rooms.domain.rooms import BREACH_ROOM_BY_ID, BREACH_ROOMS, BreachRoom
from app.modules.breach_rooms.infrastructure.database.models import (
    BreachRoomSubmissionModel,
)
from app.modules.breach_rooms.infrastructure.github.client import (
    GitHubBreachRoomClient,
    GitHubPullRequestError,
    PullRequestDraft,
    make_submission_ref,
)
from app.modules.breach_rooms.infrastructure.repositories.sqlalchemy_breach_room_repository import (
    SQLAlchemyBreachRoomSubmissionRepository,
)
from app.modules.breach_rooms.presentation.schemas.breach_room import (
    BreachRoomResponse,
    BreachRoomResultsResponse,
    BreachRoomSubmissionRequest,
    BreachRoomSubmissionResponse,
    BreachRoomSubmitResponse,
)
from app.modules.users.domain.entities.user import User

router = APIRouter()


def get_github_client(
    settings: Settings = Depends(get_settings),
) -> GitHubBreachRoomClient:
    return GitHubBreachRoomClient(
        repo=settings.breach_rooms_github_repo,
        base_branch=settings.breach_rooms_github_base_branch,
        token=settings.breach_rooms_github_token,
    )


def _room_or_404(room_id: str) -> BreachRoom:
    room = BREACH_ROOM_BY_ID.get(room_id)
    if room is None:
        raise NotFoundError("Breach room not found")
    return room


def _room_response(room: BreachRoom) -> BreachRoomResponse:
    return BreachRoomResponse(
        id=room.id,
        slug=room.slug,
        title=room.title,
        displayName=room.display_name,
        repositoryUrl=room.repository_url,
        installUrl=room.install_url,
        auditCommand=room.audit_command,
        summary=room.summary,
        contestDetails=room.contest_details,
        scope=room.scope,
        knownIssueSummary=room.known_issue_summary,
        xpReward=room.xp_reward,
    )


def _submission_response(model: BreachRoomSubmissionModel) -> BreachRoomSubmissionResponse:
    return BreachRoomSubmissionResponse(
        submissionId=model.id,
        roomId=model.room_id,
        status=model.status,
        reviewState=model.review_state,
        prUrl=model.pr_url,
        prCreationStatus=model.pr_creation_status,
        prCreationError=model.pr_creation_error,
        title=model.title,
        category=model.category,
        severity=model.severity,
        likelihood=model.likelihood,
        sourceReference=model.source_reference,
        reportMarkdown=model.report_markdown,
        createdAt=model.created_at,
        updatedAt=model.updated_at,
    )


def _submit_response(model: BreachRoomSubmissionModel) -> BreachRoomSubmitResponse:
    return BreachRoomSubmitResponse(
        submissionId=model.id,
        status=model.status,
        reviewState=model.review_state,
        prUrl=model.pr_url,
        prCreationStatus=model.pr_creation_status,
        prCreationError=model.pr_creation_error,
    )


@router.get(
    "",
    response_model=list[BreachRoomResponse],
    response_model_by_alias=True,
    summary="List breach rooms",
)
async def list_breach_rooms(
    current_user: User = Depends(get_current_user),
) -> list[BreachRoomResponse]:
    _ = current_user
    return [_room_response(room) for room in BREACH_ROOMS]


@router.get(
    "/{room_id}",
    response_model=BreachRoomResponse,
    response_model_by_alias=True,
    summary="Get breach room details",
)
async def get_breach_room(
    room_id: str,
    current_user: User = Depends(get_current_user),
) -> BreachRoomResponse:
    _ = current_user
    return _room_response(_room_or_404(room_id))


@router.get(
    "/{room_id}/submissions/me",
    response_model=list[BreachRoomSubmissionResponse],
    response_model_by_alias=True,
    summary="List my breach room submissions",
)
async def list_my_breach_room_submissions(
    room_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[BreachRoomSubmissionResponse]:
    _room_or_404(room_id)
    submissions = await SQLAlchemyBreachRoomSubmissionRepository(session).list_for_user(
        room_id=room_id,
        user_id=current_user.id,
    )
    return [_submission_response(submission) for submission in submissions]


@router.post(
    "/{room_id}/submissions",
    response_model=BreachRoomSubmitResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a breach room vulnerability",
)
async def submit_breach_room_vulnerability(
    room_id: str,
    payload: BreachRoomSubmissionRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    github_client: GitHubBreachRoomClient = Depends(get_github_client),
) -> BreachRoomSubmitResponse:
    room = _room_or_404(room_id)
    repo = SQLAlchemyBreachRoomSubmissionRepository(session)
    submission = await repo.create(
        room_id=room.id,
        user_id=current_user.id,
        wallet_address=current_user.wallet_address,
        title=payload.title,
        category=payload.category,
        severity=str(payload.severity),
        likelihood=str(payload.likelihood),
        source_reference=payload.source_reference,
        report_markdown=payload.report_markdown,
    )
    await session.commit()

    submission_ref = make_submission_ref(current_user.wallet_address or current_user.id, submission.id)
    pr_branch = f"submission/{room.id}/{submission_ref}"
    file_path = f"submissions/{room.id}/{submission_ref}.md"
    draft = PullRequestDraft(
        branch=pr_branch,
        file_path=file_path,
        title=f"[Breach Room 1] {submission.severity} - {submission.title}",
        body=_pr_body(room, current_user, submission),
        content=_submission_markdown(room, current_user, submission),
    )
    try:
        result = await github_client.create_submission_pr(draft)
        submission = await repo.mark_pr_created(
            submission,
            pr_url=result.url,
            pr_number=result.number,
            pr_branch=pr_branch,
            pr_file_path=file_path,
        )
    except GitHubPullRequestError as exc:
        submission = await repo.mark_pr_failed(
            submission,
            error=str(exc),
            pr_branch=pr_branch,
            pr_file_path=file_path,
        )
    await session.commit()
    return _submit_response(submission)


@router.get(
    "/{room_id}/results/me",
    response_model=BreachRoomResultsResponse,
    response_model_by_alias=True,
    summary="Get my breach room judging results",
)
async def get_my_breach_room_results(
    room_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> BreachRoomResultsResponse:
    _room_or_404(room_id)
    submission = await SQLAlchemyBreachRoomSubmissionRepository(session).latest_for_user(
        room_id=room_id,
        user_id=current_user.id,
    )
    if submission is None:
        return BreachRoomResultsResponse(
            status="not_submitted",
            matchedFindings=[],
            missedFindings=[],
            xpEarned=0,
            reviewerNotes="No submission has been received for this room.",
        )
    if submission.review_state != "judged":
        return BreachRoomResultsResponse(
            status=submission.review_state,
            matchedFindings=[],
            missedFindings=[],
            xpEarned=0,
            reviewerNotes=submission.pr_creation_error or "Submission is awaiting review.",
        )
    return BreachRoomResultsResponse(
        status="judged",
        matchedFindings=list(submission.matched_findings_json or []),
        missedFindings=list(submission.missed_findings_json or []),
        xpEarned=submission.xp_earned,
        reviewerNotes=submission.reviewer_notes or "",
    )


def _pr_body(room: BreachRoom, user: User, submission: BreachRoomSubmissionModel) -> str:
    return "\n".join(
        [
            "## SolBreach Submission",
            "",
            f"- Room: {room.id}",
            f"- User ID: {user.id}",
            f"- Wallet: {user.wallet_address or 'not_provided'}",
            f"- Severity: {submission.severity}",
            f"- Likelihood: {submission.likelihood}",
            f"- Category: {submission.category}",
            f"- Source reference: {submission.source_reference}",
            f"- Submission ID: {submission.id}",
        ]
    )


def _submission_markdown(
    room: BreachRoom,
    user: User,
    submission: BreachRoomSubmissionModel,
) -> str:
    return "\n\n".join(
        [
            _pr_body(room, user, submission),
            "## Report",
            submission.report_markdown,
        ]
    )
