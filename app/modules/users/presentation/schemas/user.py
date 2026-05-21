from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.modules.users.domain.entities.user import UserRole


class UserResponse(BaseModel):
    id: str
    username: str
    email: EmailStr
    role: UserRole
    wallet_address: str | None
    bio: str | None
    avatar: str | None
    xp: int
    reputation_score: int
    completed_levels: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
