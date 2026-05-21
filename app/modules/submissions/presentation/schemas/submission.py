from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.modules.submissions.domain.entities.submission import SubmissionStatus


class SubmissionResponse(BaseModel):
    id: str
    user_id: str
    level_id: str
    session_id: str
    attempt_number: int
    payload: dict[str, Any]
    status: SubmissionStatus
    verification_message: str | None
    verification_result: dict[str, Any]
    created_at: datetime | None = None
    updated_at: datetime | None = None
