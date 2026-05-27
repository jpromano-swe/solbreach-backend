from dataclasses import dataclass
from typing import Any

from app.modules.certifications.domain.entities.certification import Certification
from app.modules.levels.domain.entities.level import Level
from app.modules.levels.domain.entities.level_session import LevelSession, LevelState
from app.modules.progress.domain.entities.progress import Progress
from app.modules.submissions.domain.entities.submission import Submission


@dataclass(frozen=True, slots=True)
class LevelStatusView:
    level: Level
    state: LevelState
    session: LevelSession | None
    progress: Progress | None
    submissions: list[Submission]
    next_level_id: str | None


@dataclass(frozen=True, slots=True)
class LevelStartResult:
    level: Level
    state: LevelState
    session: LevelSession


@dataclass(frozen=True, slots=True)
class LevelSubmitResult:
    level: Level
    session: LevelSession
    submission: Submission
    progress: Progress | None
    unlocked_next_level_id: str | None
    certification: Certification | None


@dataclass(frozen=True, slots=True)
class LevelSetupResult:
    level: Level
    session: LevelSession
    challenge: dict[str, Any]
    exploit_status: str
