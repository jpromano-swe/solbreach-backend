from httpx import AsyncClient


async def register_user(client: AsyncClient, email: str = "player@example.com") -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"username": email.split("@")[0], "email": email, "password": "strong-password"},
    )
    assert response.status_code == 201


async def login_token(client: AsyncClient, email: str = "player@example.com") -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "strong-password"},
    )
    assert response.status_code == 200
    return response.json()["tokens"]["access_token"]


async def test_level_1_happy_path_unlocks_level_2(seeded_client: AsyncClient) -> None:
    await register_user(seeded_client)
    token = await login_token(seeded_client)
    headers = {"Authorization": f"Bearer {token}"}

    levels_response = await seeded_client.get("/api/v1/levels")
    assert levels_response.status_code == 200
    levels = levels_response.json()
    level_1 = next(level for level in levels if level["slug"] == "level-1-fake-mint")
    level_2 = next(level for level in levels if level["slug"] == "level-2-authority-spoofing")

    assert level_1["title"] == "Level 1: Fake Mint"
    assert level_1["vulnerability_category"] == "token_validation"
    assert level_1["difficulty"] == "easy"
    assert level_1["objectives"]
    assert level_1["instructions"]
    assert level_1["verification_requirements"]
    assert level_1["xp_reward"] == 100

    level_1_status = await seeded_client.get(
        f"/api/v1/levels/{level_1['id']}/status", headers=headers
    )
    assert level_1_status.status_code == 200
    assert level_1_status.json()["state"] == "available"
    assert level_1_status.json()["unlock_status"] == "unlocked"
    assert level_1_status.json()["submissions"] == []

    level_2_status = await seeded_client.get(
        f"/api/v1/levels/{level_2['id']}/status", headers=headers
    )
    assert level_2_status.status_code == 200
    assert level_2_status.json()["state"] == "locked"

    start_response = await seeded_client.post(
        f"/api/v1/levels/{level_1['id']}/start", headers=headers
    )
    assert start_response.status_code == 201
    assert start_response.json()["state"] == "in_progress"

    in_progress_status = await seeded_client.get(
        f"/api/v1/levels/{level_1['id']}/status", headers=headers
    )
    assert in_progress_status.json()["state"] == "in_progress"
    assert in_progress_status.json()["session"]["attempt_count"] == 0

    submit_response = await seeded_client.post(
        f"/api/v1/levels/{level_1['id']}/submit",
        headers=headers,
        json={"proof": level_1["deployment_info"]["example_proof"]},
    )
    assert submit_response.status_code == 200
    submit_data = submit_response.json()
    assert submit_data["success"] is True
    assert submit_data["data"]["submission_status"] == "VERIFIED"
    assert submit_data["data"]["level_completed"] is True
    assert submit_data["data"]["xp_awarded"] == 100
    assert submit_data["data"]["next_level_unlocked"] is True
    assert submit_data["data"]["unlocked_level_id"] == level_2["id"]

    completed_status = await seeded_client.get(
        f"/api/v1/levels/{level_1['id']}/status", headers=headers
    )
    completed_data = completed_status.json()
    assert completed_data["state"] == "completed"
    assert completed_data["xp_earned"] == 100
    assert completed_data["progress"]["xp_awarded"] == 100
    assert completed_data["submissions"][0]["status"] == "verified"

    unlocked_level_2 = await seeded_client.get(
        f"/api/v1/levels/{level_2['id']}/status", headers=headers
    )
    assert unlocked_level_2.json()["state"] == "available"

    me_response = await seeded_client.get("/api/v1/auth/me", headers=headers)
    assert me_response.json()["xp"] == 100
    assert me_response.json()["completed_levels"] == 1


async def test_level_1_invalid_submission_returns_frontend_friendly_error(
    seeded_client: AsyncClient,
) -> None:
    await register_user(seeded_client, email="badproof@example.com")
    token = await login_token(seeded_client, email="badproof@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    level_1 = next(
        level
        for level in (await seeded_client.get("/api/v1/levels")).json()
        if level["slug"] == "level-1-fake-mint"
    )

    await seeded_client.post(f"/api/v1/levels/{level_1['id']}/start", headers=headers)
    rejected_response = await seeded_client.post(
        f"/api/v1/levels/{level_1['id']}/submit",
        headers=headers,
        json={
            "proof": {
                "transaction_signature": "wrong-signature-level-1-abcdef",
                "transaction_succeeded": True,
                "token_balances": {"attacker_token_delta": 5, "vault_delta": -5},
            }
        },
    )
    assert rejected_response.status_code == 200
    body = rejected_response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_SUBMISSION"
    assert body["error"]["message"] == "Verification failed"
    assert body["error"]["details"]["verified"] is False

    failed_status = await seeded_client.get(
        f"/api/v1/levels/{level_1['id']}/status", headers=headers
    )
    assert failed_status.json()["state"] == "failed"
    assert failed_status.json()["submissions"][0]["status"] == "rejected"


async def test_submission_requires_started_unlocked_level(seeded_client: AsyncClient) -> None:
    await register_user(seeded_client, email="locked@example.com")
    token = await login_token(seeded_client, email="locked@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    levels = (await seeded_client.get("/api/v1/levels")).json()
    level_1 = next(level for level in levels if level["slug"] == "level-1-fake-mint")
    level_2 = next(level for level in levels if level["slug"] == "level-2-authority-spoofing")

    locked_response = await seeded_client.post(
        f"/api/v1/levels/{level_2['id']}/submit",
        headers=headers,
        json={"proof": level_2["deployment_info"]["example_proof"]},
    )
    assert locked_response.status_code == 403
    assert locked_response.json()["error"]["code"] == "INVALID_SUBMISSION"

    not_started_response = await seeded_client.post(
        f"/api/v1/levels/{level_1['id']}/submit",
        headers=headers,
        json={"proof": level_1["deployment_info"]["example_proof"]},
    )
    assert not_started_response.status_code == 409
    assert not_started_response.json()["error"]["code"] == "LEVEL_NOT_STARTED"
