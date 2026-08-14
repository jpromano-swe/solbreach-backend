from httpx import AsyncClient

from app.shared.blockchain import BlockchainTransaction


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


async def _complete_level(
    client: AsyncClient,
    fake_blockchain: dict[str, BlockchainTransaction],
    headers: dict[str, str],
    level_id: str,
    wallet_address: str,
    tx_signature: str,
) -> None:
    start = await client.post(f"/api/v1/levels/{level_id}/start", headers=headers)
    assert start.status_code == 201

    setup = await client.post(
        f"/api/v1/levels/{level_id}/setup",
        headers=headers,
        json={"wallet_address": wallet_address},
    )
    assert setup.status_code == 200
    setup_data = setup.json()
    challenge = setup_data["challenge"]
    fake_blockchain[tx_signature] = BlockchainTransaction(
        signature=tx_signature,
        network="devnet",
        exists=True,
        succeeded=True,
        slot=123,
        signers=[challenge["wallet_address"]],
        account_keys=challenge["required_accounts"],
    )
    submit = await client.post(
        f"/api/v1/levels/{level_id}/submit",
        headers=headers,
        json={
            "transaction_signature": tx_signature,
            "wallet_address": challenge["wallet_address"],
            "level_session_id": setup_data["level_session_id"],
        },
    )
    assert submit.status_code == 200
    assert submit.json()["success"] is True


async def test_badges_me_returns_all_slots_and_seen_is_guarded(
    seeded_client: AsyncClient,
) -> None:
    await _register_user(seeded_client, "badges-empty@example.com")
    token = await _login_token(seeded_client, "badges-empty@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = await seeded_client.get("/api/v1/badges/me", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert [badge["slug"] for badge in body["badges"]] == [
        "level-1-illusionist",
        "level-2-identity-thief",
        "level-3-trojan-horse",
        "level-4-data-matching",
        "level-5-time-traveler",
        "power-user",
    ]
    assert all(badge["earned"] is False for badge in body["badges"])
    assert body["summary"] == {"earned": 0, "total": 6, "powerUserEarned": False}

    seen = await seeded_client.post("/api/v1/badges/level-1-illusionist/seen", headers=headers)
    assert seen.status_code == 409


async def test_level_badges_do_not_award_power_user(
    seeded_client: AsyncClient,
    fake_blockchain: dict[str, BlockchainTransaction],
) -> None:
    await _register_user(seeded_client, "badges-levels@example.com")
    token = await _login_token(seeded_client, "badges-levels@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    levels = (await seeded_client.get("/api/v1/levels")).json()
    level_1 = next(level for level in levels if level["slug"] == "level-1-fake-mint")
    level_2 = next(level for level in levels if level["slug"] == "level-2-authority-spoofing")
    level_3 = next(level for level in levels if level["slug"] == "level-3-unchecked-cpi")

    await _complete_level(
        seeded_client,
        fake_blockchain,
        headers,
        level_1["id"],
        "BadgeOneWallet111111111111111111111111111",
        "badge-level-one-tx",
    )
    badges = (await seeded_client.get("/api/v1/badges/me", headers=headers)).json()["badges"]
    level_1_badge = next(badge for badge in badges if badge["slug"] == "level-1-illusionist")
    assert level_1_badge["earned"] is True
    assert level_1_badge["seenAt"] is None

    seen = await seeded_client.post("/api/v1/badges/level-1-illusionist/seen", headers=headers)
    assert seen.status_code == 200
    seen_at = seen.json()["seenAt"]
    assert seen_at is not None
    seen_again = await seeded_client.post(
        "/api/v1/badges/level-1-illusionist/seen", headers=headers
    )
    assert seen_again.status_code == 200
    assert seen_again.json()["seenAt"] == seen_at

    await _complete_level(
        seeded_client,
        fake_blockchain,
        headers,
        level_2["id"],
        "BadgeTwoWallet111111111111111111111111111",
        "badge-level-two-tx",
    )
    await _complete_level(
        seeded_client,
        fake_blockchain,
        headers,
        level_3["id"],
        "BadgeThreeWallet1111111111111111111111111",
        "badge-level-three-tx",
    )
    body = (await seeded_client.get("/api/v1/badges/me", headers=headers)).json()
    earned = {badge["slug"]: badge for badge in body["badges"] if badge["earned"]}
    assert set(earned) == {
        "level-1-illusionist",
        "level-2-identity-thief",
        "level-3-trojan-horse",
    }
    power_user = next(badge for badge in body["badges"] if badge["slug"] == "power-user")
    assert power_user["earned"] is False
    assert power_user["seenAt"] is None
    assert body["summary"] == {"earned": 3, "total": 6, "powerUserEarned": False}

    power_user_seen = await seeded_client.post("/api/v1/badges/power-user/seen", headers=headers)
    assert power_user_seen.status_code == 409
