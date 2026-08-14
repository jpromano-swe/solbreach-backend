from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Severity(StrEnum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class Likelihood(StrEnum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class BreachRoomResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    slug: str
    title: str
    display_name: str = Field(alias="displayName")
    repository_url: str = Field(alias="repositoryUrl")
    install_url: str = Field(alias="installUrl")
    audit_command: str = Field(alias="auditCommand")
    summary: str
    contest_details: list[str] = Field(alias="contestDetails")
    scope: list[str]
    known_issue_summary: list[str] = Field(alias="knownIssueSummary")
    xp_reward: int = Field(alias="xpReward")


class BreachRoomSubmissionRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    category: str = Field(min_length=2, max_length=120)
    severity: Severity
    likelihood: Likelihood
    source_reference: str = Field(alias="sourceReference", min_length=1, max_length=500)
    report_markdown: str = Field(alias="reportMarkdown", min_length=100, max_length=50_000)

    model_config = ConfigDict(populate_by_name=True)


class BreachRoomSubmissionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    submission_id: str = Field(alias="submissionId")
    room_id: str = Field(alias="roomId")
    status: str
    review_state: str = Field(alias="reviewState")
    pr_url: str | None = Field(alias="prUrl")
    pr_creation_status: str = Field(alias="prCreationStatus")
    pr_creation_error: str | None = Field(alias="prCreationError")
    title: str
    category: str
    severity: Severity
    likelihood: Likelihood
    source_reference: str = Field(alias="sourceReference")
    report_markdown: str = Field(alias="reportMarkdown")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class BreachRoomSubmitResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    submission_id: str = Field(alias="submissionId")
    status: str
    review_state: str = Field(alias="reviewState")
    pr_url: str | None = Field(alias="prUrl")
    pr_creation_status: str = Field(alias="prCreationStatus")
    pr_creation_error: str | None = Field(alias="prCreationError")


class BreachRoomFindingResult(BaseModel):
    title: str
    severity: Severity
    reference: str | None = None


class BreachRoomResultsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    matched_findings: list[BreachRoomFindingResult] = Field(alias="matchedFindings")
    missed_findings: list[BreachRoomFindingResult] = Field(alias="missedFindings")
    xp_earned: int = Field(alias="xpEarned")
    reviewer_notes: str = Field(alias="reviewerNotes")
