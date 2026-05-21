from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.submissions.domain.entities.submission import Submission, SubmissionStatus
from app.modules.submissions.domain.repositories.submission_repository import SubmissionRepository
from app.modules.submissions.infrastructure.database.models import SubmissionModel


class SQLAlchemySubmissionRepository(SubmissionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, submission: Submission) -> Submission:
        model = SubmissionModel(
            id=submission.id,
            user_id=submission.user_id,
            level_id=submission.level_id,
            session_id=submission.session_id,
            attempt_number=submission.attempt_number,
            payload=submission.payload,
            status=submission.status.value,
            verification_message=submission.verification_message,
            verification_result=submission.verification_result,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def update(self, submission: Submission) -> Submission:
        model = await self._session.get(SubmissionModel, submission.id)
        if model is None:
            raise ValueError("Submission not found")
        model.status = submission.status.value
        model.verification_message = submission.verification_message
        model.verification_result = submission.verification_result
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def list_for_user(self, user_id: str, limit: int, offset: int) -> list[Submission]:
        result = await self._session.execute(
            select(SubmissionModel)
            .where(SubmissionModel.user_id == user_id)
            .order_by(SubmissionModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [self._to_entity(model) for model in result.scalars().all()]

    async def list_for_user_level(self, user_id: str, level_id: str) -> list[Submission]:
        result = await self._session.execute(
            select(SubmissionModel)
            .where(SubmissionModel.user_id == user_id, SubmissionModel.level_id == level_id)
            .order_by(SubmissionModel.created_at.desc())
        )
        return [self._to_entity(model) for model in result.scalars().all()]

    async def count_for_user_level(self, user_id: str, level_id: str) -> int:
        result = await self._session.execute(
            select(func.count(SubmissionModel.id)).where(
                SubmissionModel.user_id == user_id,
                SubmissionModel.level_id == level_id,
            )
        )
        return int(result.scalar_one())

    @staticmethod
    def _to_entity(model: SubmissionModel) -> Submission:
        return Submission(
            id=model.id,
            user_id=model.user_id,
            level_id=model.level_id,
            session_id=model.session_id,
            attempt_number=model.attempt_number,
            payload=model.payload,
            status=SubmissionStatus(model.status),
            verification_message=model.verification_message,
            verification_result=model.verification_result,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
