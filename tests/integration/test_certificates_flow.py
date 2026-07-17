from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy import select

from app.modules.certifications.infrastructure.database.models import CertificationModel
from app.modules.users.infrastructure.database.models import UserModel


async def _register_user(client: AsyncClient, email: str) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"username": email.split("@")[0], "email": email, "password": "strong-password"},
    )
    assert response.status_code == 201


async def _login_token(client: AsyncClient, email: str) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "strong-password"},
    )
    assert response.status_code == 200
    return response.json()["tokens"]["access_token"]


async def _set_wallet(session_factory, email: str, wallet_address: str) -> str:
    async with session_factory() as session:
        result = await session.execute(select(UserModel).where(UserModel.email == email))
        user = result.scalar_one()
        user.wallet_address = wallet_address
        await session.commit()
        return user.id


async def test_certificates_me_returns_level_slots(client_with_session_factory) -> None:
    client, session_factory = client_with_session_factory
    email = "certificates-empty@example.com"
    wallet = "CertEmptyWallet111111111111111111111111111"
    await _register_user(client, email)
    token = await _login_token(client, email)
    await _set_wallet(session_factory, email, wallet)

    response = await client.get(
        "/api/v1/certificates/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["walletAddress"] == wallet
    assert body["summary"] == {"minted": 0, "total": 3}
    assert [certificate["certificateId"] for certificate in body["certificates"]] == [
        "solbreach-level-1",
        "solbreach-level-2",
        "solbreach-level-3",
    ]
    assert all(certificate["status"] == "locked" for certificate in body["certificates"])
    assert all(certificate["minted"] is False for certificate in body["certificates"])
    assert body["certificates"][0]["metadataUri"] == (
        "https://beta.solbreach.com/certificates/metadata/level-1.json"
    )
    assert body["certificates"][0]["imageUri"] == (
        "https://beta.solbreach.com/certificates/level-1.png"
    )


async def test_certificates_me_returns_minted_certificate_metadata(
    client_with_session_factory,
) -> None:
    client, session_factory = client_with_session_factory
    email = "certificates-minted@example.com"
    wallet = "CertMintedWallet11111111111111111111111111"
    minted_at = datetime(2026, 7, 13, tzinfo=UTC)
    await _register_user(client, email)
    token = await _login_token(client, email)
    user_id = await _set_wallet(session_factory, email, wallet)

    async with session_factory() as session:
        session.add(
            CertificationModel(
                user_id=user_id,
                slug="solbreach-level-1",
                title="The Illusionist",
                description="Certificate awarded for completing SolBreach Level 1.",
                metadata_json={"certificate_id": "solbreach-level-1"},
                unlock_status="unlocked",
                mint_status="minted",
                wallet_address=wallet,
                asset_id="compressed-nft-asset-address",
                certificate_pda="certificate-pda-address",
                metadata_uri="https://beta.solbreach.com/certificates/metadata/level-1.json",
                minted_at=minted_at,
                unlocked_at=minted_at,
            )
        )
        await session.commit()

    response = await client.get(
        "/api/v1/certificates/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == {"minted": 1, "total": 3}
    certificate = body["certificates"][0]
    assert certificate["certificateId"] == "solbreach-level-1"
    assert certificate["certificateNumber"] == 1
    assert certificate["level"] == 1
    assert certificate["title"] == "The Illusionist"
    assert certificate["status"] == "minted"
    assert certificate["minted"] is True
    assert certificate["mintedAt"] == "2026-07-13T00:00:00Z"
    assert certificate["assetId"] == "compressed-nft-asset-address"
    assert certificate["certificatePda"] == "certificate-pda-address"
    assert certificate["metadataUri"] == "https://beta.solbreach.com/certificates/metadata/level-1.json"
    assert certificate["imageUri"] == "https://beta.solbreach.com/certificates/level-1.png"
