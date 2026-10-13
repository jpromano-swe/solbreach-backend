import time
from uuid import uuid4

import pytest
from solders.keypair import Keypair

from app.modules.certifications.presentation.schemas.mint_authorization import (
    MintAuthorizationRequest,
)
from tests.integration.test_certificates_flow import _login_token, _register_user, _set_wallet


def signed_request(wallet, level=1, issued_at=None):
    body = dict(
        player=str(wallet.pubkey()),
        level=level,
        cluster="devnet",
        issued_at=issued_at if issued_at is not None else int(time.time()),
        nonce=uuid4().hex,
        signature="1" * 64,
    )
    message = MintAuthorizationRequest(**body).signing_message()
    body["signature"] = str(wallet.sign_message(message.encode()))
    return body


async def setup_wallet(client, session_factory):
    email = f"mint-{uuid4().hex[:8]}@example.com"
    wallet = Keypair()
    await _register_user(client, email)
    token = await _login_token(client, email)
    await _set_wallet(session_factory, email, str(wallet.pubkey()))
    return wallet, {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("level", [0, 1, 2, 3])
async def test_every_level_requires_session(client, level):
    response = await client.post(
        "/api/v1/certificates/mint-authorization", json=signed_request(Keypair(), level)
    )
    assert response.status_code == 401


async def test_authorization_is_signed_wallet_bound_and_single_use(client_with_session_factory):
    client, session_factory = client_with_session_factory
    wallet, headers = await setup_wallet(client, session_factory)
    other = signed_request(Keypair())
    assert (
        await client.post("/api/v1/certificates/mint-authorization", headers=headers, json=other)
    ).status_code == 403
    body = signed_request(wallet)
    tampered = {**body, "level": 2}
    assert (
        await client.post("/api/v1/certificates/mint-authorization", headers=headers, json=tampered)
    ).status_code == 401
    response = await client.post(
        "/api/v1/certificates/mint-authorization", headers=headers, json=body
    )
    assert response.status_code == 200
    assert response.json() == {
        "authorized": True,
        "wallet_address": str(wallet.pubkey()),
        "level": 1,
    }
    assert (
        await client.post("/api/v1/certificates/mint-authorization", headers=headers, json=body)
    ).status_code == 409


async def test_mint_authorization_expires_and_rejects_other_clusters(client_with_session_factory):
    client, session_factory = client_with_session_factory
    wallet, headers = await setup_wallet(client, session_factory)
    for timestamp in (int(time.time()) - 301, int(time.time()) + 60):
        response = await client.post(
            "/api/v1/certificates/mint-authorization",
            headers=headers,
            json=signed_request(wallet, issued_at=timestamp),
        )
        assert response.status_code == 403
    body = {**signed_request(wallet), "cluster": "mainnet-beta"}
    assert (
        await client.post("/api/v1/certificates/mint-authorization", headers=headers, json=body)
    ).status_code == 422


async def test_mint_rate_limit_is_shared_between_levels(client_with_session_factory):
    client, session_factory = client_with_session_factory
    wallet, headers = await setup_wallet(client, session_factory)
    for index in range(5):
        response = await client.post(
            "/api/v1/certificates/mint-authorization",
            headers=headers,
            json=signed_request(wallet, level=index % 4),
        )
        assert response.status_code == 200
    response = await client.post(
        "/api/v1/certificates/mint-authorization", headers=headers, json=signed_request(wallet)
    )
    assert response.status_code == 429
