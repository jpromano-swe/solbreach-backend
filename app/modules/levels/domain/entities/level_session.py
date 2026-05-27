from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class LevelState(StrEnum):
    LOCKED = "locked"
    AVAILABLE = "available"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ExploitStatus(StrEnum):
    NOT_STARTED = "not_started"
    SETUP_READY = "setup_ready"
    TX_SUBMITTED = "tx_submitted"
    VERIFIED = "verified"
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
    setup_at: datetime | None = None
    exploit_status: ExploitStatus = ExploitStatus.NOT_STARTED
    wallet_address: str | None = None
    challenge_context: dict[str, Any] = field(default_factory=dict)
    tx_signature: str | None = None
    verified_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
