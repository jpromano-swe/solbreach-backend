from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class LevelState(StrEnum):
    LOCKED = "locked"
    AVAILABLE = "available"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(slots=True)
class LevelSession:
    id: str
    user_id: str
    level_id: str
    state: LevelState
    attempt_count: int
    started_at: datetime
    completed_at: datetime | None = None
    last_submitted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
