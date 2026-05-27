from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

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
    setup_at: datetime | None = None
    exploit_status: str
    wallet_address: str | None = None
    challenge_context: dict[str, Any] = Field(default_factory=dict)
    tx_signature: str | None = None
    verified_at: datetime | None = None


class LevelExecutionMetadata(BaseModel):
    setup_required: bool
    network: str
    setup_endpoint: str | None = None
    submit_proof_fields: list[str] = Field(default_factory=list)
    execution_mode: str = "wallet_signed"


class LevelStatusResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "state": "in_progress",
                    "unlock_status": "unlocked",
                    "available": True,
                    "completed": False,
                    "progress": None,
                    "submissions": [],
                    "xp_awarded": 0,
                    "xp_earned": 0,
                    "next_level_id": "8bb6a9be-cc76-57ed-910f-99c73321cd36",
                    "exploit_status": "setup_ready",
                    "challenge_context": {
                        "network": "devnet",
                        "level_session_id": "fba5ffad-de30-4d6e-abda-0ffc84df23b7",
                        "fake_mint": "3VHckAvpqS7rU5fh6Fgd53v9XB5ebCZoneU3jLSRjgK1",
                        "fake_vault": "Gkmd1oWTCERJ55PqsDNNf41JatUPNwmKMA5NQ7t5ToB8",
                    },
                }
            ]
        }
    )

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
    exploit_status: str | None = None
    challenge_context: dict[str, Any] = Field(default_factory=dict)


class LevelStartResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "state": "in_progress",
                    "session": {
                        "id": "fba5ffad-de30-4d6e-abda-0ffc84df23b7",
                        "level_id": "96d2111d-bb01-5a1b-9536-57331fed473e",
                        "state": "in_progress",
                        "attempt_count": 0,
                        "exploit_status": "not_started",
                    },
                    "execution": {
                        "setup_required": True,
                        "network": "devnet",
                        "setup_endpoint": (
                            "/api/v1/levels/"
                            "96d2111d-bb01-5a1b-9536-57331fed473e/setup"
                        ),
                        "submit_proof_fields": [
                            "transaction_signature",
                            "wallet_address",
                            "level_session_id",
                        ],
                        "execution_mode": "wallet_signed_demo_transaction",
                    },
                }
            ]
        }
    )

    level: LevelResponse
    state: str
    session: LevelSessionResponse
    execution: LevelExecutionMetadata | None = None


class LevelSubmitRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "transaction_signature": (
                        "5UBXMiJ4txXnK9BNXkhkXyGjVD8EG9UsQYo3Tf1SRQp6vCVs6F9rt"
                        "D1V3QAH4L5i4hJ8yQpT9hEiS94UnnLv4B9M"
                    ),
                    "wallet_address": "DemoWallet111111111111111111111111111111111",
                    "level_session_id": "fba5ffad-de30-4d6e-abda-0ffc84df23b7",
                }
            ]
        }
    )

    proof: dict[str, Any] | None = Field(
        default=None,
        examples=[
            {
                "transaction_signature": "demo-signature-level-0-abcdef",
                "transaction_succeeded": True,
                "pda_state": {"completed_levels_0": True},
            }
        ],
    )
    transaction_signature: str | None = None
    wallet_address: str | None = None
    level_session_id: str | None = None

    def to_proof(self) -> dict[str, Any]:
        if self.proof is not None:
            return dict(self.proof)
        proof: dict[str, Any] = {}
        if self.transaction_signature is not None:
            proof["transaction_signature"] = self.transaction_signature
        if self.wallet_address is not None:
            proof["wallet_address"] = self.wallet_address
        if self.level_session_id is not None:
            proof["level_session_id"] = self.level_session_id
        return proof


class LevelSetupRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"wallet_address": "DemoWallet111111111111111111111111111111111"}
            ]
        }
    )

    wallet_address: str = Field(min_length=32, max_length=64)


class LevelSetupResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "level_id": "96d2111d-bb01-5a1b-9536-57331fed473e",
                    "level_session_id": "fba5ffad-de30-4d6e-abda-0ffc84df23b7",
                    "exploit_status": "setup_ready",
                    "challenge": {
                        "network": "devnet",
                        "wallet_address": "DemoWallet111111111111111111111111111111111",
                        "program_id": "11111111111111111111111111111111",
                        "official_mint": "7aPAqFTyYx9pDumrJjVYddtdLyqXJZCWkaghrBfCojZq",
                        "official_vault": "EA9GzZ4GCrLU6Wmh4AEfa1AZQywrfz6sfgYbzxksmj26",
                        "fake_mint": "3VHckAvpqS7rU5fh6Fgd53v9XB5ebCZoneU3jLSRjgK1",
                        "fake_vault": "Gkmd1oWTCERJ55PqsDNNf41JatUPNwmKMA5NQ7t5ToB8",
                        "challenge_pda": "7V2e1roVwkmkdUVTSv3AiMj6PANfGP24nFp8jXsffFfk",
                        "attacker_token_account": (
                            "5CDB6o3mZX3hsZK3jQresBe5hJmW1ejjKnDQqA2rR87n"
                        ),
                        "required_accounts": [
                            "11111111111111111111111111111111",
                            "7aPAqFTyYx9pDumrJjVYddtdLyqXJZCWkaghrBfCojZq",
                            "EA9GzZ4GCrLU6Wmh4AEfa1AZQywrfz6sfgYbzxksmj26",
                            "3VHckAvpqS7rU5fh6Fgd53v9XB5ebCZoneU3jLSRjgK1",
                            "Gkmd1oWTCERJ55PqsDNNf41JatUPNwmKMA5NQ7t5ToB8",
                            "7V2e1roVwkmkdUVTSv3AiMj6PANfGP24nFp8jXsffFfk",
                            "5CDB6o3mZX3hsZK3jQresBe5hJmW1ejjKnDQqA2rR87n",
                            "DemoWallet111111111111111111111111111111111",
                        ],
                        "exploit_parameters": {
                            "vulnerability": "fake_mint",
                            "mode": "wallet_signed_demo_transaction",
                            "demo_mode": True,
                            "proof_fields": [
                                "transaction_signature",
                                "wallet_address",
                                "level_session_id",
                            ],
                            "verification_focus": [
                                "transaction_exists",
                                "transaction_succeeded",
                                "wallet_signed",
                                "required_accounts_included",
                                "session_binding",
                                "replay_protection",
                            ],
                        },
                    },
                }
            ]
        }
    )

    level_id: str
    level_session_id: str
    exploit_status: str
    challenge: dict[str, Any]


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
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "success": True,
                    "data": {
                        "submission_status": "VERIFIED",
                        "level_completed": True,
                        "xp_awarded": 100,
                        "next_level_unlocked": True,
                        "unlocked_level_id": "8bb6a9be-cc76-57ed-910f-99c73321cd36",
                    },
                    "error": None,
                },
                {
                    "success": False,
                    "data": None,
                    "error": {
                        "code": "INVALID_SUBMISSION",
                        "message": "Verification failed",
                        "details": {
                            "verified": False,
                            "message": "Verification failed",
                            "checks": [
                                {
                                    "name": "solana_transaction",
                                    "passed": False,
                                    "message": "Transaction was not found on devnet",
                                    "details": {},
                                }
                            ],
                        },
                    },
                },
            ]
        }
    )

    success: bool
    data: LevelSubmitSuccessData | None = None
    error: LevelSubmitErrorData | None = None
