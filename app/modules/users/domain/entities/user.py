from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"
    RESEARCHER = "researcher"
    REVIEWER = "reviewer"


@dataclass(slots=True)
class User:
    id: str
    username: str
    email: str
    hashed_password: str
    role: UserRole
    wallet_address: str | None
    bio: str | None
    avatar: str | None
    xp: int
    reputation_score: int
    completed_levels: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
