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


async def _claim(
    client: AsyncClient,
    headers: dict[str, str],
    session_id: str,
    target_wallet_address: str | None = None,
    instruction_name: str | None = "claim_rewards",
):
    parameters = {
        "position_account_ref": "stake_position",
        "reward_vault_ref": "reward_vault",
        "destination_account_ref": "attacker_reward_account",
    }
    if instruction_name is not None:
        parameters["instruction_name"] = instruction_name
    if target_wallet_address is not None:
        parameters["target_wallet_address"] = target_wallet_address
    return await client.post(
        f"/api/v1/research-labs/sessions/{session_id}/transactions",
        headers=headers,
        json={
            "action_type": "CLAIM_REWARDS",
            "parameters": parameters,
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
    account_refs = {account["ref"] for account in accounts_response.json()["data"]["accounts"]}
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


async def test_rl2_explorer_snapshot_contract(seeded_client: AsyncClient) -> None:
    await _register_user(seeded_client, "rl2-explorer@example.com")
    token = await _login_token(seeded_client, "rl2-explorer@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    session_id = await _create_rl2_session(seeded_client, headers)

    unauthenticated = await seeded_client.get(
        f"/api/v1/research-labs/sessions/{session_id}/explorer"
    )
    assert unauthenticated.status_code in {401, 403}

    response = await seeded_client.get(
        f"/api/v1/research-labs/sessions/{session_id}/explorer",
        headers=headers,
    )
    assert response.status_code == 200
    explorer = response.json()["data"]
    assert explorer["sessionId"] == session_id
    assert explorer["network"] == {"name": "SolBreach SVM", "kind": "sandbox"}
    assert explorer["program"]["ref"] == "yield_hijack"
    assert explorer["program"]["interfaceSource"] == "lab_idl"
    assert explorer["program"]["idl"]["address"] == explorer["program"]["address"]
    assert explorer["program"]["idl"]["metadata"]["address"] == explorer["program"]["address"]
    assert {instruction["name"] for instruction in explorer["program"]["idl"]["instructions"]} == {
        "stake",
        "claim_rewards",
    }

    account_refs = {account["ref"] for account in explorer["accounts"]}
    assert "shared_position" not in account_refs
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
    accounts_by_ref = {account["ref"]: account for account in explorer["accounts"]}
    program_address = explorer["program"]["address"]
    assert accounts_by_ref["pool_config"]["ownerProgram"] == program_address
    assert accounts_by_ref["pool_config"]["data"]["totalRewardsPaid"] == 14_325
    assert accounts_by_ref["stake_position"]["ownerProgram"] == program_address
    assert accounts_by_ref["stake_position"]["accountType"] == "StakePosition"
    assert accounts_by_ref["stake_position"]["data"]["pendingRewards"] == 12_500
    assert explorer["rewardCandidates"] == [
        {
            "walletAddress": accounts_by_ref["stake_position"]["data"]["baselineOwner"],
            "positionAddress": accounts_by_ref["stake_position"]["address"],
            "pendingRewards": 12_500,
        }
    ]
    assert explorer["totalRewardsPaid"] == 14_325

    repeat = (
        await seeded_client.get(
            f"/api/v1/research-labs/sessions/{session_id}/explorer",
            headers=headers,
        )
    ).json()["data"]
    assert repeat["program"]["address"] == program_address
    assert repeat["accounts"] == explorer["accounts"]

    other_session_id = await _create_rl2_session(seeded_client, headers)
    other_explorer = (
        await seeded_client.get(
            f"/api/v1/research-labs/sessions/{other_session_id}/explorer",
            headers=headers,
        )
    ).json()["data"]
    assert other_explorer["program"]["address"] != program_address
    assert (
        other_explorer["rewardCandidates"][0]["positionAddress"]
        != explorer["rewardCandidates"][0]["positionAddress"]
    )


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

    initial_explorer = (
        await seeded_client.get(
            f"/api/v1/research-labs/sessions/{session_id}/explorer",
            headers=headers,
        )
    ).json()["data"]
    victim_wallet = initial_explorer["rewardCandidates"][0]["walletAddress"]

    missing_instruction = await _claim(
        seeded_client, headers, session_id, victim_wallet, instruction_name=None
    )
    assert missing_instruction.status_code == 200
    assert missing_instruction.json()["data"]["executionStatus"] == "failure"
    assert missing_instruction.json()["data"]["protocolState"]["lastRejectedReason"] == (
        "INSTRUCTION_NAME_REQUIRED"
    )
    assert (
        missing_instruction.json()["data"]["protocolState"]["position"]["pendingRewards"] == 12_500
    )

    invalid_instruction = await _claim(
        seeded_client,
        headers,
        session_id,
        victim_wallet,
        instruction_name="claimReward",
    )
    assert invalid_instruction.status_code == 200
    assert invalid_instruction.json()["data"]["executionStatus"] == "failure"
    assert invalid_instruction.json()["data"]["protocolState"]["lastRejectedReason"] == (
        "INVALID_INSTRUCTION_NAME"
    )
    assert (
        invalid_instruction.json()["data"]["protocolState"]["position"]["pendingRewards"] == 12_500
    )

    missing_target = await _claim(seeded_client, headers, session_id)
    assert missing_target.status_code == 200
    assert missing_target.json()["data"]["executionStatus"] == "failure"
    assert missing_target.json()["data"]["protocolState"]["lastRejectedReason"] == (
        "TARGET_WALLET_REQUIRED"
    )
    assert missing_target.json()["data"]["protocolState"]["position"]["pendingRewards"] == 12_500

    invalid_target = await _claim(
        seeded_client, headers, session_id, "11111111111111111111111111111111"
    )
    assert invalid_target.status_code == 200
    assert invalid_target.json()["data"]["executionStatus"] == "failure"
    assert invalid_target.json()["data"]["protocolState"]["lastRejectedReason"] == (
        "INVALID_TARGET_WALLET"
    )
    assert invalid_target.json()["data"]["protocolState"]["position"]["pendingRewards"] == 12_500

    early_claim = await _claim(seeded_client, headers, session_id, victim_wallet)
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
    assert stake_state["pool"]["totalRewardsPaid"] == 14_325
    assert stake_state["totalRewardsPaid"] == 14_325
    assert stake_state["rewardsClaimedTotal"] == 0
    assert stake_state["attacker"]["stakeBalance"] == 99

    stake_only_verify = await seeded_client.post(
        f"/api/v1/research-labs/sessions/{session_id}/verify-objective", headers=headers
    )
    assert stake_only_verify.status_code == 200
    assert stake_only_verify.json()["data"]["impactVerified"] is False
    after_stake_explorer = (
        await seeded_client.get(
            f"/api/v1/research-labs/sessions/{session_id}/explorer",
            headers=headers,
        )
    ).json()["data"]
    assert after_stake_explorer["rewardCandidates"][0]["walletAddress"] == victim_wallet
    assert after_stake_explorer["rewardCandidates"][0]["pendingRewards"] == 12_500

    claim = await _claim(seeded_client, headers, session_id, victim_wallet)
    assert claim.status_code == 200
    claim_data = claim.json()["data"]
    assert claim_data["executionStatus"] == "success"
    assert claim_data["parameters"]["instruction_name"] == "claim_rewards"
    claim_state = claim_data["protocolState"]
    assert claim_state["attacker"]["rewardBalance"] == 12_500
    assert claim_state["pool"]["rewardVaultBalance"] == 487_500
    assert claim_state["position"]["pendingRewards"] == 0
    assert claim_state["rewardsClaimedTotal"] == 12_500
    assert claim_state["pool"]["totalRewardsPaid"] == 26_825
    assert claim_state["totalRewardsPaid"] == 26_825
    after_claim_explorer = (
        await seeded_client.get(
            f"/api/v1/research-labs/sessions/{session_id}/explorer",
            headers=headers,
        )
    ).json()["data"]
    assert after_claim_explorer["rewardCandidates"] == []
    assert after_claim_explorer["totalRewardsPaid"] == 26_825

    second_claim = await _claim(seeded_client, headers, session_id, victim_wallet)
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

    transactions = await seeded_client.get(
        f"/api/v1/research-labs/sessions/{session_id}/transactions",
        headers=headers,
    )
    assert transactions.status_code == 200
    tx_items = transactions.json()["data"]["transactions"]
    assert len(tx_items) >= 6
    logs = await seeded_client.get(
        f"/api/v1/research-labs/sessions/{session_id}/transactions/{claim_data['transactionRef']}/logs",
        headers=headers,
    )
    assert logs.status_code == 200
    assert "Pending rewards claimed" in " ".join(logs.json()["data"]["logs"])

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

    explorer = await seeded_client.get(
        f"/api/v1/research-labs/sessions/{session_id}/explorer",
        headers=intruder_headers,
    )
    assert explorer.status_code == 403
