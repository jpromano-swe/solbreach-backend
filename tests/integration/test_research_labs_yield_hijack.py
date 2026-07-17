from httpx import AsyncClient


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


async def _create_rl2_session(client: AsyncClient, headers: dict[str, str]) -> str:
    response = await client.post("/api/v1/research-labs/rl2-yield-hijack/sessions", headers=headers)
    assert response.status_code == 201
    return response.json()["data"]["session_id"]


async def _stake(client: AsyncClient, headers: dict[str, str], session_id: str, amount: int):
    return await client.post(
        f"/api/v1/research-labs/sessions/{session_id}/transactions",
        headers=headers,
        json={
            "action_type": "STAKE",
            "parameters": {
                "amount": amount,
                "source_account_ref": "attacker_stake_account",
                "stake_vault_ref": "stake_vault",
                "position_account_ref": "stake_position",
            },
        },
    )


async def _claim(client: AsyncClient, headers: dict[str, str], session_id: str):
    return await client.post(
        f"/api/v1/research-labs/sessions/{session_id}/transactions",
        headers=headers,
        json={
            "action_type": "CLAIM_REWARDS",
            "parameters": {
                "position_account_ref": "stake_position",
                "reward_vault_ref": "reward_vault",
                "destination_account_ref": "attacker_reward_account",
            },
        },
    )


async def test_rl2_session_initializes_with_shared_position_derivation(
    seeded_client: AsyncClient,
) -> None:
    await _register_user(seeded_client, "rl2-setup@example.com")
    token = await _login_token(seeded_client, "rl2-setup@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    catalog = (await seeded_client.get("/api/v1/research-labs", headers=headers)).json()["data"]
    assert any(lab["id"] == "rl2-yield-hijack" for lab in catalog)
    session_id = await _create_rl2_session(seeded_client, headers)

    accounts_response = await seeded_client.get(
        f"/api/v1/research-labs/sessions/{session_id}/accounts",
        headers=headers,
    )
    assert accounts_response.status_code == 200
    account_refs = {
        account["ref"] for account in accounts_response.json()["data"]["accounts"]
    }
    assert account_refs == {
        "pool_config",
        "pool_authority",
        "stake_mint",
        "reward_mint",
        "stake_vault",
        "reward_vault",
        "stake_position",
        "attacker_stake_account",
        "attacker_reward_account",
        "victim_stake_account",
        "victim_reward_account",
    }
    assert "shared_position" not in account_refs

    position_response = await seeded_client.get(
        f"/api/v1/research-labs/sessions/{session_id}/accounts/stake_position",
        headers=headers,
    )
    assert position_response.status_code == 200
    position = position_response.json()["data"]["account"]["data"]
    assert position["owner"] == position["baselineOwner"]
    assert position["stakedAmount"] == 50_000
    assert position["pendingRewards"] == 12_500
    assert (
        position["derivations"]["victim_position"]["address"]
        == position["derivations"]["attacker_position"]["address"]
    )

    repeat = await seeded_client.get(
        f"/api/v1/research-labs/sessions/{session_id}/accounts/stake_position",
        headers=headers,
    )
    assert repeat.json()["data"]["account"]["data"]["address"] == position["address"]

    other_session_id = await _create_rl2_session(seeded_client, headers)
    other_position = (
        await seeded_client.get(
            f"/api/v1/research-labs/sessions/{other_session_id}/accounts/stake_position",
            headers=headers,
        )
    ).json()["data"]["account"]["data"]
    assert other_position["address"] != position["address"]


async def test_rl2_stake_claim_and_verify_flow(seeded_client: AsyncClient) -> None:
    await _register_user(seeded_client, "rl2-flow@example.com")
    token = await _login_token(seeded_client, "rl2-flow@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    session_id = await _create_rl2_session(seeded_client, headers)

    before_verify = await seeded_client.post(
        f"/api/v1/research-labs/sessions/{session_id}/verify-objective", headers=headers
    )
    assert before_verify.status_code == 200
    assert before_verify.json()["data"]["impactVerified"] is False

    early_claim = await _claim(seeded_client, headers, session_id)
    assert early_claim.status_code == 200
    assert early_claim.json()["data"]["executionStatus"] == "failure"
    assert early_claim.json()["data"]["protocolState"]["lastRejectedReason"] == (
        "INVALID_POSITION_OWNER"
    )

    zero_stake = await _stake(seeded_client, headers, session_id, 0)
    assert zero_stake.status_code == 200
    assert zero_stake.json()["data"]["executionStatus"] == "failure"
    assert zero_stake.json()["data"]["protocolState"]["lastRejectedReason"] == "INVALID_AMOUNT"

    excessive_stake = await _stake(seeded_client, headers, session_id, 101)
    assert excessive_stake.status_code == 200
    assert excessive_stake.json()["data"]["executionStatus"] == "failure"
    assert excessive_stake.json()["data"]["protocolState"]["lastRejectedReason"] == (
        "INSUFFICIENT_STAKE_BALANCE"
    )

    stake = await _stake(seeded_client, headers, session_id, 1)
    assert stake.status_code == 200
    stake_data = stake.json()["data"]
    assert stake_data["executionStatus"] == "success"
    stake_state = stake_data["protocolState"]
    assert stake_state["position"]["owner"] == stake_state["attacker"]["wallet"]
    assert stake_state["position"]["stakedAmount"] == 50_001
    assert stake_state["position"]["pendingRewards"] == 12_500
    assert stake_state["pool"]["stakeVaultBalance"] == 50_001
    assert stake_state["attacker"]["stakeBalance"] == 99

    stake_only_verify = await seeded_client.post(
        f"/api/v1/research-labs/sessions/{session_id}/verify-objective", headers=headers
    )
    assert stake_only_verify.status_code == 200
    assert stake_only_verify.json()["data"]["impactVerified"] is False

    claim = await _claim(seeded_client, headers, session_id)
    assert claim.status_code == 200
    claim_data = claim.json()["data"]
    assert claim_data["executionStatus"] == "success"
    claim_state = claim_data["protocolState"]
    assert claim_state["attacker"]["rewardBalance"] == 12_500
    assert claim_state["pool"]["rewardVaultBalance"] == 487_500
    assert claim_state["position"]["pendingRewards"] == 0
    assert claim_state["rewardsClaimedTotal"] == 12_500

    second_claim = await _claim(seeded_client, headers, session_id)
    assert second_claim.status_code == 200
    assert second_claim.json()["data"]["executionStatus"] == "failure"
    assert second_claim.json()["data"]["protocolState"]["lastRejectedReason"] == (
        "NO_REWARDS_AVAILABLE"
    )

    position_before_verify = (
        await seeded_client.get(
            f"/api/v1/research-labs/sessions/{session_id}/accounts/stake_position",
            headers=headers,
        )
    ).json()["data"]["account"]["data"]
    verified = await seeded_client.post(
        f"/api/v1/research-labs/sessions/{session_id}/verify-objective", headers=headers
    )
    assert verified.status_code == 200
    verified_data = verified.json()["data"]
    assert verified_data["impactVerified"] is True
    assert verified_data["evidence"]["vulnerabilityClass"] == "STATIC_PDA"
    assert verified_data["evidence"]["impact"]["attackerStaked"] == 1
    assert verified_data["evidence"]["impact"]["rewardsClaimed"] == 12_500
    position_after_verify = (
        await seeded_client.get(
            f"/api/v1/research-labs/sessions/{session_id}/accounts/stake_position",
            headers=headers,
        )
    ).json()["data"]["account"]["data"]
    assert position_after_verify == position_before_verify


async def test_rl2_session_ownership_is_enforced(seeded_client: AsyncClient) -> None:
    await _register_user(seeded_client, "rl2-owner@example.com")
    owner_token = await _login_token(seeded_client, "rl2-owner@example.com")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    session_id = await _create_rl2_session(seeded_client, owner_headers)

    await _register_user(seeded_client, "rl2-intruder@example.com")
    intruder_token = await _login_token(seeded_client, "rl2-intruder@example.com")
    intruder_headers = {"Authorization": f"Bearer {intruder_token}"}

    response = await _stake(seeded_client, intruder_headers, session_id, 1)
    assert response.status_code == 403
