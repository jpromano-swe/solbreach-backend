from typing import Any
from uuid import uuid4

from app.core.exceptions.domain import ConflictError
from app.modules.levels.domain.entities.level import Level, LevelStage
from app.modules.levels.domain.repositories.level_repository import LevelRepository


class LevelAlreadyExistsError(ConflictError):
    code = "LEVEL_ALREADY_EXISTS"


class CreateLevelUseCase:
    def __init__(self, levels: LevelRepository) -> None:
        self._levels = levels

    async def execute(
        self,
        slug: str,
        title: str,
        description: str,
        order: int,
        stage: LevelStage,
        vulnerability_id: str | None,
        vulnerability_category: str,
        difficulty: str,
        objectives: list[str],
        instructions: str,
        verification_requirements: list[str],
        repository_url: str | None,
        resources: list[dict[str, Any]],
        verification_config: dict[str, Any],
        deployment_info: dict[str, Any],
        xp_reward: int,
    ) -> Level:
        if await self._levels.get_by_slug(slug):
            raise LevelAlreadyExistsError("Level slug already exists")
        return await self._levels.create(
            Level(
                id=str(uuid4()),
                slug=slug,
                title=title,
                description=description,
                order=order,
                stage=stage,
                vulnerability_id=vulnerability_id,
                vulnerability_category=vulnerability_category,
                difficulty=difficulty,
                objectives=objectives,
                instructions=instructions,
                verification_requirements=verification_requirements,
                repository_url=repository_url,
                resources=resources,
                verification_config=verification_config,
                deployment_info=deployment_info,
                xp_reward=xp_reward,
            )
        )
