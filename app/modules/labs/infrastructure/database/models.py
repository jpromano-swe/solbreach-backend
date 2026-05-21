from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base, SoftDeleteMixin, UUIDTimestampMixin


class LabModel(UUIDTimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "labs"

    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True, nullable=False)
    sandbox_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
