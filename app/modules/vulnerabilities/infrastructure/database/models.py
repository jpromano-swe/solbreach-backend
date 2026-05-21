from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base, SoftDeleteMixin, UUIDTimestampMixin


class VulnerabilityModel(UUIDTimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "vulnerabilities"

    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
