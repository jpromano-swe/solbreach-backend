from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class SubmissionStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


@dataclass(slots=True)
class Submission:
    id: str
    user_id: str
    level_id: str
    session_id: str
    attempt_number: int
    payload: dict[str, Any] = field(default_factory=dict)
    status: SubmissionStatus = SubmissionStatus.PENDING
    verification_message: str | None = None
    verification_result: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
