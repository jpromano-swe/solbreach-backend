from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base, SoftDeleteMixin, UUIDTimestampMixin


class UserModel(UUIDTimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(30), default="user", index=True, nullable=False)
    wallet_address: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    bio: Mapped[str | None] = mapped_column(Text)
    avatar: Mapped[str | None] = mapped_column(String(500))
    xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reputation_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_levels: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
