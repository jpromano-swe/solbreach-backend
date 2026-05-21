from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.modules.certifications.presentation.schemas.certification import CertificationResponse
from app.modules.levels.domain.entities.level import LevelStage
from app.modules.progress.presentation.schemas.progress import ProgressResponse
from app.modules.submissions.presentation.schemas.submission import SubmissionResponse


class LevelCreateRequest(BaseModel):
    slug: str = Field(min_length=3, max_length=100, pattern=r"^[a-z0-9_\\-]+$")
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10)
    order: int = Field(ge=0)
    stage: LevelStage
    vulnerability_id: str | None = None
    vulnerability_category: str = Field(default="", max_length=100)
    difficulty: str = Field(default="easy", max_length=40)
    objectives: list[str] = Field(default_factory=list)
    instructions: str = Field(default="", max_length=5000)
    verification_requirements: list[str] = Field(default_factory=list)
    repository_url: str | None = None
    resources: list[dict[str, Any]] = Field(default_factory=list)
    verification_config: dict[str, Any] = Field(default_factory=dict)
    deployment_info: dict[str, Any] = Field(default_factory=dict)
    xp_reward: int = Field(default=0, ge=0)


class LevelResponse(BaseModel):
    id: str
    slug: str
    title: str
    description: str
    order: int
    stage: LevelStage
    vulnerability_id: str | None
    vulnerability_category: str
    difficulty: str
    objectives: list[str]
    instructions: str
    verification_requirements: list[str]
    repository_url: str | None
    resources: list[dict[str, Any]]
    verification_config: dict[str, Any]
    deployment_info: dict[str, Any]
    xp_reward: int
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class LevelSessionResponse(BaseModel):
    id: str
    user_id: str
    level_id: str
    state: str
    attempt_count: int
    started_at: datetime
    completed_at: datetime | None = None
    last_submitted_at: datetime | None = None


class LevelStatusResponse(BaseModel):
    level: LevelResponse
    state: str
    unlock_status: str
    available: bool
    session: LevelSessionResponse | None
    completed: bool
    progress: ProgressResponse | None
    submissions: list[SubmissionResponse]
    xp_awarded: int
    xp_earned: int
    next_level_id: str | None


class LevelStartResponse(BaseModel):
    level: LevelResponse
    state: str
    session: LevelSessionResponse


class LevelSubmitRequest(BaseModel):
    proof: dict[str, Any] = Field(
        default_factory=dict,
        examples=[
            {
                "transaction_signature": "demo-signature-level-0-abcdef",
                "transaction_succeeded": True,
                "pda_state": {"completed_levels_0": True},
            }
        ],
    )


class LevelSubmitSuccessData(BaseModel):
    submission_status: str
    level_completed: bool
    xp_awarded: int
    next_level_unlocked: bool
    unlocked_level_id: str | None
    submission: SubmissionResponse
    progress: ProgressResponse | None
    certification: CertificationResponse | None


class LevelSubmitErrorData(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class LevelSubmitResponse(BaseModel):
    success: bool
    data: LevelSubmitSuccessData | None = None
    error: LevelSubmitErrorData | None = None
