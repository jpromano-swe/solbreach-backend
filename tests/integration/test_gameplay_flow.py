from httpx import AsyncClient

from app.shared.blockchain import BlockchainTransaction


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


async def complete_executable_level(
    client: AsyncClient,
    fake_blockchain: dict[str, BlockchainTransaction],
    headers: dict[str, str],
    level_id: str,
    wallet_address: str,
    tx_signature: str,
) -> dict:
    start_response = await client.post(f"/api/v1/levels/{level_id}/start", headers=headers)
    assert start_response.status_code == 201
    assert start_response.json()["state"] == "in_progress"
    assert start_response.json()["execution"]["setup_required"] is True

    setup_response = await client.post(
        f"/api/v1/levels/{level_id}/setup",
        headers=headers,
        json={"wallet_address": wallet_address},
    )
    assert setup_response.status_code == 200
    setup_data = setup_response.json()
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
    submit_response = await client.post(
        f"/api/v1/levels/{level_id}/submit",
        headers=headers,
        json={
            "transaction_signature": tx_signature,
            "wallet_address": challenge["wallet_address"],
            "level_session_id": setup_data["level_session_id"],
        },
    )
    assert submit_response.status_code == 200
    body = submit_response.json()
    assert body["success"] is True
    return body


async def test_level_1_happy_path_unlocks_level_2(
    seeded_client: AsyncClient, fake_blockchain: dict[str, BlockchainTransaction]
) -> None:
    await register_user(seeded_client)
    token = await login_token(seeded_client)
    headers = {"Authorization": f"Bearer {token}"}

    levels_response = await seeded_client.get("/api/v1/levels")
    assert levels_response.status_code == 200
    levels = levels_response.json()
    level_1 = next(level for level in levels if level["slug"] == "level-1-fake-mint")
    level_2 = next(level for level in levels if level["slug"] == "level-2-authority-spoofing")

    assert level_1["title"] == "Level 1: The Illusionist"
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
    assert start_response.json()["execution"]["setup_required"] is True

    setup_response = await seeded_client.post(
        f"/api/v1/levels/{level_1['id']}/setup",
        headers=headers,
        json={"wallet_address": "DemoWallet111111111111111111111111111111111"},
    )
    assert setup_response.status_code == 200
    setup_data = setup_response.json()
    assert setup_data["exploit_status"] == "setup_ready"
    challenge = setup_data["challenge"]

    in_progress_status = await seeded_client.get(
        f"/api/v1/levels/{level_1['id']}/status", headers=headers
    )
    assert in_progress_status.json()["state"] == "in_progress"
    assert in_progress_status.json()["session"]["attempt_count"] == 0
    assert in_progress_status.json()["exploit_status"] == "setup_ready"

    tx_signature = "valid-level-1-signature-abcdef"
    fake_blockchain[tx_signature] = BlockchainTransaction(
        signature=tx_signature,
        network="devnet",
        exists=True,
        succeeded=True,
        slot=123,
        signers=[challenge["wallet_address"]],
        account_keys=challenge["required_accounts"],
    )

    submit_response = await seeded_client.post(
        f"/api/v1/levels/{level_1['id']}/submit",
        headers=headers,
        json={
            "transaction_signature": tx_signature,
            "wallet_address": challenge["wallet_address"],
            "level_session_id": setup_data["level_session_id"],
        },
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
    assert completed_data["exploit_status"] == "verified"
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


async def test_level_2_happy_path_unlocks_level_3_and_certification_minting(
    seeded_client: AsyncClient, fake_blockchain: dict[str, BlockchainTransaction]
) -> None:
    await register_user(seeded_client, email="level-two@example.com")
    token = await login_token(seeded_client, email="level-two@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    levels = (await seeded_client.get("/api/v1/levels")).json()
    level_1 = next(level for level in levels if level["slug"] == "level-1-fake-mint")
    level_2 = next(level for level in levels if level["slug"] == "level-2-authority-spoofing")
    level_3 = next(level for level in levels if level["slug"] == "level-3-unchecked-cpi")

    await complete_executable_level(
        seeded_client,
        fake_blockchain,
        headers,
        level_1["id"],
        "LevelTwoPrereqWallet11111111111111111111111",
        "level-two-prereq-signature-abcdef",
    )

    level_2_status = await seeded_client.get(
        f"/api/v1/levels/{level_2['id']}/status", headers=headers
    )
    assert level_2_status.status_code == 200
    assert level_2_status.json()["state"] == "available"

    start_response = await seeded_client.post(
        f"/api/v1/levels/{level_2['id']}/start", headers=headers
    )
    assert start_response.status_code == 201
    assert start_response.json()["execution"]["execution_mode"] == "wallet_signed_demo_transaction"

    setup_response = await seeded_client.post(
        f"/api/v1/levels/{level_2['id']}/setup",
        headers=headers,
        json={"wallet_address": "CommanderWallet11111111111111111111111111"},
    )
    assert setup_response.status_code == 200
    setup_data = setup_response.json()
    challenge = setup_data["challenge"]
    assert setup_data["exploit_status"] == "setup_ready"
    assert challenge["exploit_parameters"]["vulnerability"] == "static_pda_commander_hijack"
    assert challenge["expected_commander_after_hijack"] == challenge["wallet_address"]
    assert "commander_registry_pda" in challenge
    assert "hijacked_commander_pda" in challenge

    tx_signature = "valid-level-2-signature-abcdef"
    fake_blockchain[tx_signature] = BlockchainTransaction(
        signature=tx_signature,
        network="devnet",
        exists=True,
        succeeded=True,
        slot=456,
        signers=[challenge["wallet_address"]],
        account_keys=challenge["required_accounts"],
    )

    submit_response = await seeded_client.post(
        f"/api/v1/levels/{level_2['id']}/submit",
        headers=headers,
        json={
            "transaction_signature": tx_signature,
            "wallet_address": challenge["wallet_address"],
            "level_session_id": setup_data["level_session_id"],
        },
    )
    assert submit_response.status_code == 200
    submit_data = submit_response.json()
    assert submit_data["success"] is True
    assert submit_data["data"]["submission_status"] == "VERIFIED"
    assert submit_data["data"]["level_completed"] is True
    assert submit_data["data"]["xp_awarded"] == 250
    assert submit_data["data"]["next_level_unlocked"] is True
    assert submit_data["data"]["unlocked_level_id"] == level_3["id"]
    certification = submit_data["data"]["certification"]
    assert certification["slug"] == "static-pda-commander-hijack"
    assert certification["unlock_status"] == "unlocked"
    assert certification["mint_status"] == "not_minted"
    assert certification["metadata"]["minting_enabled"] is True

    level_3_status = await seeded_client.get(
        f"/api/v1/levels/{level_3['id']}/status", headers=headers
    )
    assert level_3_status.json()["state"] == "available"

    me_response = await seeded_client.get("/api/v1/auth/me", headers=headers)
    assert me_response.json()["xp"] == 350
    assert me_response.json()["completed_levels"] == 2


async def test_level_3_happy_path_unlocks_level_4_and_certification_minting(
    seeded_client: AsyncClient, fake_blockchain: dict[str, BlockchainTransaction]
) -> None:
    await register_user(seeded_client, email="level-three@example.com")
    token = await login_token(seeded_client, email="level-three@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    levels = (await seeded_client.get("/api/v1/levels")).json()
    level_1 = next(level for level in levels if level["slug"] == "level-1-fake-mint")
    level_2 = next(level for level in levels if level["slug"] == "level-2-authority-spoofing")
    level_3 = next(level for level in levels if level["slug"] == "level-3-unchecked-cpi")
    level_4 = next(level for level in levels if level["slug"] == "level-4-advanced-bounty-drainer")

    await complete_executable_level(
        seeded_client,
        fake_blockchain,
        headers,
        level_1["id"],
        "LevelThreePrereqOneWallet1111111111111111111",
        "level-three-prereq-one-signature-abcdef",
    )
    await complete_executable_level(
        seeded_client,
        fake_blockchain,
        headers,
        level_2["id"],
        "LevelThreePrereqTwoWallet1111111111111111111",
        "level-three-prereq-two-signature-abcdef",
    )

    level_3_status = await seeded_client.get(
        f"/api/v1/levels/{level_3['id']}/status", headers=headers
    )
    assert level_3_status.status_code == 200
    assert level_3_status.json()["state"] == "available"

    start_response = await seeded_client.post(
        f"/api/v1/levels/{level_3['id']}/start", headers=headers
    )
    assert start_response.status_code == 201
    assert start_response.json()["execution"]["execution_mode"] == "wallet_signed_demo_transaction"

    setup_response = await seeded_client.post(
        f"/api/v1/levels/{level_3['id']}/setup",
        headers=headers,
        json={"wallet_address": "TrojanWallet111111111111111111111111111111"},
    )
    assert setup_response.status_code == 200
    setup_data = setup_response.json()
    challenge = setup_data["challenge"]
    assert setup_data["exploit_status"] == "setup_ready"
    assert challenge["exploit_parameters"]["vulnerability"] == (
        "arbitrary_cpi_delegated_signer_abuse"
    )
    assert challenge["exploit_parameters"]["expected_sequence"] == [
        "target",
        "signer",
        "vault",
        "reward",
    ]
    assert "guild_authority_pda" in challenge
    assert "bounty_vault_pda" in challenge
    assert "attacker_cpi_program" in challenge
    assert "player_reward_account" in challenge

    tx_signature = "valid-level-3-signature-abcdef"
    fake_blockchain[tx_signature] = BlockchainTransaction(
        signature=tx_signature,
        network="devnet",
        exists=True,
        succeeded=True,
        slot=789,
        signers=[challenge["wallet_address"]],
        account_keys=challenge["required_accounts"],
    )

    submit_response = await seeded_client.post(
        f"/api/v1/levels/{level_3['id']}/submit",
        headers=headers,
        json={
            "transaction_signature": tx_signature,
            "wallet_address": challenge["wallet_address"],
            "level_session_id": setup_data["level_session_id"],
        },
    )
    assert submit_response.status_code == 200
    submit_data = submit_response.json()
    assert submit_data["success"] is True
    assert submit_data["data"]["submission_status"] == "VERIFIED"
    assert submit_data["data"]["level_completed"] is True
    assert submit_data["data"]["xp_awarded"] == 300
    assert submit_data["data"]["next_level_unlocked"] is True
    assert submit_data["data"]["unlocked_level_id"] == level_4["id"]
    certification = submit_data["data"]["certification"]
    assert certification["slug"] == "arbitrary-cpi-delegated-signer-abuse"
    assert certification["title"] == "Arbitrary CPI Delegated Signer Abuse"
    assert certification["unlock_status"] == "unlocked"
    assert certification["mint_status"] == "not_minted"
    assert certification["metadata"]["completed_level_order"] == 3
    assert certification["metadata"]["minting_enabled"] is True

    level_4_status = await seeded_client.get(
        f"/api/v1/levels/{level_4['id']}/status", headers=headers
    )
    assert level_4_status.json()["state"] == "available"

    me_response = await seeded_client.get("/api/v1/auth/me", headers=headers)
    assert me_response.json()["xp"] == 650
    assert me_response.json()["completed_levels"] == 3


async def test_level_1_invalid_submission_returns_frontend_friendly_error(
    seeded_client: AsyncClient,
    fake_blockchain: dict[str, BlockchainTransaction],
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
    setup_response = await seeded_client.post(
        f"/api/v1/levels/{level_1['id']}/setup",
        headers=headers,
        json={"wallet_address": "BadProofWallet111111111111111111111111111"},
    )
    challenge = setup_response.json()["challenge"]
    fake_blockchain["missing-account-level-1-abcdef"] = BlockchainTransaction(
        signature="missing-account-level-1-abcdef",
        network="devnet",
        exists=True,
        succeeded=True,
        slot=123,
        signers=[challenge["wallet_address"]],
        account_keys=challenge["required_accounts"][:-1],
    )
    rejected_response = await seeded_client.post(
        f"/api/v1/levels/{level_1['id']}/submit",
        headers=headers,
        json={
            "transaction_signature": "missing-account-level-1-abcdef",
            "wallet_address": challenge["wallet_address"],
            "level_session_id": setup_response.json()["level_session_id"],
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


async def test_level_1_rejects_reused_transaction_signature(
    seeded_client: AsyncClient, fake_blockchain: dict[str, BlockchainTransaction]
) -> None:
    await register_user(seeded_client, email="replay-one@example.com")
    token_1 = await login_token(seeded_client, email="replay-one@example.com")
    headers_1 = {"Authorization": f"Bearer {token_1}"}
    await register_user(seeded_client, email="replay-two@example.com")
    token_2 = await login_token(seeded_client, email="replay-two@example.com")
    headers_2 = {"Authorization": f"Bearer {token_2}"}

    level_1 = next(
        level
        for level in (await seeded_client.get("/api/v1/levels")).json()
        if level["slug"] == "level-1-fake-mint"
    )

    await seeded_client.post(f"/api/v1/levels/{level_1['id']}/start", headers=headers_1)
    setup_1 = await seeded_client.post(
        f"/api/v1/levels/{level_1['id']}/setup",
        headers=headers_1,
        json={"wallet_address": "ReplayOneWallet1111111111111111111111111"},
    )
    challenge_1 = setup_1.json()["challenge"]
    tx_signature = "reused-level-1-signature-abcdef"
    fake_blockchain[tx_signature] = BlockchainTransaction(
        signature=tx_signature,
        network="devnet",
        exists=True,
        succeeded=True,
        slot=123,
        signers=[challenge_1["wallet_address"]],
        account_keys=challenge_1["required_accounts"],
    )
    verified = await seeded_client.post(
        f"/api/v1/levels/{level_1['id']}/submit",
        headers=headers_1,
        json={
            "transaction_signature": tx_signature,
            "wallet_address": challenge_1["wallet_address"],
            "level_session_id": setup_1.json()["level_session_id"],
        },
    )
    assert verified.status_code == 200
    assert verified.json()["success"] is True

    await seeded_client.post(f"/api/v1/levels/{level_1['id']}/start", headers=headers_2)
    setup_2 = await seeded_client.post(
        f"/api/v1/levels/{level_1['id']}/setup",
        headers=headers_2,
        json={"wallet_address": "ReplayTwoWallet1111111111111111111111111"},
    )
    replay = await seeded_client.post(
        f"/api/v1/levels/{level_1['id']}/submit",
        headers=headers_2,
        json={
            "transaction_signature": tx_signature,
            "wallet_address": setup_2.json()["challenge"]["wallet_address"],
            "level_session_id": setup_2.json()["level_session_id"],
        },
    )
    assert replay.status_code == 403
    assert replay.json()["error"]["code"] == "INVALID_SUBMISSION"
