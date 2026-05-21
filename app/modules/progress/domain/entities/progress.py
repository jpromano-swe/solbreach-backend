from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Progress:
    id: str
    user_id: str
    level_id: str
    xp_awarded: int
    completed_at: datetime
    created_at: datetime | None = None
    updated_at: datetime | None = None
