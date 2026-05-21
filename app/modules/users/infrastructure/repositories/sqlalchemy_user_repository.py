from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.domain.entities.user import User, UserRole
from app.modules.users.domain.repositories.user_repository import UserRepository
from app.modules.users.infrastructure.database.models import UserModel


class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user: User) -> User:
        model = UserModel(
            id=user.id,
            username=user.username,
            email=user.email,
            hashed_password=user.hashed_password,
            role=user.role.value,
            wallet_address=user.wallet_address,
            bio=user.bio,
            avatar=user.avatar,
            xp=user.xp,
            reputation_score=user.reputation_score,
            completed_levels=user.completed_levels,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def get_by_id(self, user_id: str) -> User | None:
        model = await self._session.get(UserModel, user_id)
        if model is None or model.deleted_at is not None:
            return None
        return self._to_entity(model)

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == email, UserModel.deleted_at.is_(None))
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_username(self, username: str) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.username == username, UserModel.deleted_at.is_(None))
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list(self, limit: int, offset: int) -> list[User]:
        result = await self._session.execute(
            select(UserModel)
            .where(UserModel.deleted_at.is_(None))
            .order_by(UserModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [self._to_entity(model) for model in result.scalars().all()]

    async def update(self, user: User) -> User:
        model = await self._session.get(UserModel, user.id)
        if model is None:
            raise ValueError("User model not found")
        model.username = user.username
        model.email = user.email
        model.role = user.role.value
        model.wallet_address = user.wallet_address
        model.bio = user.bio
        model.avatar = user.avatar
        model.xp = user.xp
        model.reputation_score = user.reputation_score
        model.completed_levels = user.completed_levels
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    @staticmethod
    def _to_entity(model: UserModel) -> User:
        return User(
            id=model.id,
            username=model.username,
            email=model.email,
            hashed_password=model.hashed_password,
            role=UserRole(model.role),
            wallet_address=model.wallet_address,
            bio=model.bio,
            avatar=model.avatar,
            xp=model.xp,
            reputation_score=model.reputation_score,
            completed_levels=model.completed_levels,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
