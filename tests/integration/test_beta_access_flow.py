from datetime import UTC, datetime, timedelta
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import select

from app.modules.beta_access.application.use_cases.beta_access import hash_access_code
from app.modules.beta_access.infrastructure.database.models import BetaAccessCodeModel
from app.modules.analytics.infrastructure.database.models import AnalyticsEventModel


WALLET_ONE = "WalletOne111111111111111111111111111111"
WALLET_TWO = "WalletTwo111111111111111111111111111111"
WALLET_THREE = "WalletThree111111111111111111111111111"
WALLET_FOUR = "WalletFour1111111111111111111111111111"


async def _seed_code(
    session_factory,
    code: str,
    *,
    max_redemptions: int = 1,
    redemption_count: int = 0,
    expires_at: datetime | None = None,
) -> None:
    async with session_factory() as session:
        session.add(
            BetaAccessCodeModel(
                id=str(uuid4()),
                code_hash=hash_access_code(code),
                label="test",
                status="active",
                max_redemptions=max_redemptions,
                redemption_count=redemption_count,
                expires_at=expires_at,
            )
        )
        await session.commit()


async def test_beta_access_status_returns_no_access_for_unknown_wallet(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/api/v1/beta-access/status",
        params={"wallet_address": WALLET_ONE},
    )

    assert response.status_code == 200
    assert response.json() == {
        "walletAddress": WALLET_ONE,
        "hasAccess": False,
        "accessSource": None,
        "status": "none",
    }


async def test_beta_access_request_accepts_wallet_only_and_dedupes(
    client: AsyncClient,
) -> None:
    first = await client.post(
        "/api/v1/beta-access/requests",
        json={"walletAddress": WALLET_ONE, "nameOrHandle": "anon"},
    )
    assert first.status_code == 201
    first_body = first.json()
    assert first_body["status"] == "pending"
    assert first_body["message"] == "Beta access request received."

    second = await client.post(
        "/api/v1/beta-access/requests",
        json={"walletAddress": WALLET_ONE},
    )
    assert second.status_code == 200
    assert second.json()["requestId"] == first_body["requestId"]
    assert second.json()["message"] == "Beta access request already exists."


async def test_beta_access_redeem_code_grants_wallet_access(
    client_with_session_factory,
) -> None:
    client, session_factory = client_with_session_factory
    await _seed_code(session_factory, "BETA-123")

    redeem = await client.post(
        "/api/v1/beta-access/redeem",
        json={"walletAddress": WALLET_TWO, "code": "beta 123"},
    )
    assert redeem.status_code == 200
    assert redeem.json() == {
        "walletAddress": WALLET_TWO,
        "hasAccess": True,
        "accessSource": "access_code",
        "status": "approved",
    }

    status = await client.get(
        "/api/v1/beta-access/status",
        params={"walletAddress": WALLET_TWO},
    )
    assert status.status_code == 200
    assert status.json()["hasAccess"] is True


async def test_beta_access_redeem_rejects_invalid_expired_and_exhausted_codes(
    client_with_session_factory,
) -> None:
    client, session_factory = client_with_session_factory
    await _seed_code(
        session_factory,
        "OLD-CODE",
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    await _seed_code(
        session_factory,
        "USED-CODE",
        max_redemptions=1,
        redemption_count=1,
    )

    invalid = await client.post(
        "/api/v1/beta-access/redeem",
        json={"walletAddress": WALLET_ONE, "code": "missing"},
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "INVALID_ACCESS_CODE"

    expired = await client.post(
        "/api/v1/beta-access/redeem",
        json={"walletAddress": WALLET_THREE, "code": "old-code"},
    )
    assert expired.status_code == 400
    assert expired.json()["error"]["code"] == "EXPIRED_ACCESS_CODE"

    exhausted = await client.post(
        "/api/v1/beta-access/redeem",
        json={"walletAddress": WALLET_FOUR, "code": "used-code"},
    )
    assert exhausted.status_code == 409
    assert exhausted.json()["error"]["code"] == "EXHAUSTED_ACCESS_CODE"

    async with session_factory() as session:
        result = await session.execute(
            select(AnalyticsEventModel)
            .where(AnalyticsEventModel.event_type == "beta_access_code_failed")
            .order_by(AnalyticsEventModel.occurred_at.asc())
        )
        events = list(result.scalars().all())

    assert [event.metadata_json["failureReason"] for event in events] == [
        "invalid",
        "expired",
        "exhausted",
    ]
    assert all("missing" not in str(event.metadata_json).lower() for event in events)
    assert all("old-code" not in str(event.metadata_json).lower() for event in events)
    assert all("used-code" not in str(event.metadata_json).lower() for event in events)
