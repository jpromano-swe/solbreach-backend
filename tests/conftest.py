import os
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-secret-with-at-least-32-bytes"
os.environ["SOLBREACH_ADMIN_PASSWORD"] = "admin-password"

from app.core.database.base import Base  # noqa: E402
from app.core.database.models import *  # noqa: F403,E402
from app.core.database.session import get_db_session  # noqa: E402
from app.core.dependencies.blockchain import get_blockchain_client  # noqa: E402
from app.main import create_app  # noqa: E402
from app.scripts.seed_dev_data import seed_development_data  # noqa: E402
from app.shared.blockchain import BlockchainTransaction  # noqa: E402

FAKE_BLOCKCHAIN_TRANSACTIONS: dict[str, BlockchainTransaction] = {}


class FakeBlockchainClient:
    async def get_transaction(self, signature: str) -> BlockchainTransaction | None:
        return FAKE_BLOCKCHAIN_TRANSACTIONS.get(signature)


@pytest.fixture()
def fake_blockchain() -> dict[str, BlockchainTransaction]:
    FAKE_BLOCKCHAIN_TRANSACTIONS.clear()
    return FAKE_BLOCKCHAIN_TRANSACTIONS


@pytest.fixture()
async def client() -> AsyncGenerator[AsyncClient, None]:
    async for test_client in _build_client(seed=False):
        yield test_client


@pytest.fixture()
async def seeded_client() -> AsyncGenerator[AsyncClient, None]:
    async for test_client in _build_client(seed=True):
        yield test_client


async def _build_client(seed: bool) -> AsyncGenerator[AsyncClient, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    if seed:
        async with session_factory() as session:
            await seed_development_data(session)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_blockchain_client] = lambda: FakeBlockchainClient()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as test_client:
        yield test_client

    await engine.dispose()
