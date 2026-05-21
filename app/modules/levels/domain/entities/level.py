from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class LevelStage(StrEnum):
    VULNERABILITIES = "vulnerabilities"
    RESEARCH_LABS = "research_labs"
    BREACH_ROOMS = "breach_rooms"


@dataclass(slots=True)
class Level:
    id: str
    slug: str
    title: str
    description: str
    order: int
    stage: LevelStage
    vulnerability_id: str | None
    vulnerability_category: str = ""
    difficulty: str = "easy"
    instructions: str = ""
    repository_url: str | None = None
    objectives: list[str] = field(default_factory=list)
    verification_requirements: list[str] = field(default_factory=list)
    resources: list[dict[str, Any]] = field(default_factory=list)
    verification_config: dict[str, Any] = field(default_factory=dict)
    deployment_info: dict[str, Any] = field(default_factory=dict)
    xp_reward: int = 0
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None
