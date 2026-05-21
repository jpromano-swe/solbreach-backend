from app.modules.submissions.domain.entities.submission import Submission
from app.modules.submissions.domain.repositories.submission_repository import SubmissionRepository


class ListUserSubmissionsUseCase:
    def __init__(self, submissions: SubmissionRepository) -> None:
        self._submissions = submissions

    async def execute(self, user_id: str, limit: int, offset: int) -> list[Submission]:
        return await self._submissions.list_for_user(user_id, limit, offset)
