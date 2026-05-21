from datetime import datetime

from pydantic import BaseModel


class ProgressResponse(BaseModel):
    id: str
    user_id: str
    level_id: str
    xp_awarded: int
    completed_at: datetime
    created_at: datetime | None = None
    updated_at: datetime | None = None
