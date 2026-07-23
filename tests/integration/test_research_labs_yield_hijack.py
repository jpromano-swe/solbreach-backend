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
                "source_account_ref": "user_stake_account",
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
        "destination_account_ref": "user_reward_account",
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


def _correct_rl2_finding_review_answers() -> dict[str, str]:
    return {
        "q1_vulnerability_category": "static_pda_missing_user_identity",
        "q2_derivation_identity": "staker_public_key",
        "q3_exploit_sequence": "existing_rewards_same_pda_stake_overwrite_claim",
        "q4_preserved_value": "pending_rewards_preserved",
        "q5_impact": "unauthorized_preexisting_reward_claim",
        "q6_evidence": ("owner_changed_after_stake,position_pda_collision,reward_delta_matches"),
        "q7_severity": "high",
        "q8_recommended_fix": "scope_pda_by_pool_and_user",
    }


def _accepted_rl2_report_fields(verified_evidence_refs: list[str]) -> dict:
    return {
        "titleOptionId": "static_staking_position_reward_hijack",
        "severityOptionId": "high",
        "likelihoodOptionId": "high",
        "categoryOptionId": "static_pda",
        "rootCauseOptionId": "static_pda_missing_user_seed",
        "proofOfImpactOptionId": "position_owner_overwrite_reward_claim",
        "recommendedMitigationOptionId": "scope_position_pda_by_pool_and_user",
        "verifiedEvidenceRefs": verified_evidence_refs,
        "optionalNotes": "Verified static PDA reward hijack.",
    }


PARTICIPANT_REFS = {f"pool_participant_{index}_wallet" for index in range(1, 6)}


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
        *PARTICIPANT_REFS,
        "user_stake_account",
        "user_reward_account",
        "existing_staker_stake_account",
        "existing_staker_reward_account",
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
        position["derivations"]["existing_staker_position"]["address"]
        == position["derivations"]["user_position"]["address"]
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
        *PARTICIPANT_REFS,
        "user_stake_account",
        "user_reward_account",
        "existing_staker_stake_account",
        "existing_staker_reward_account",
    }
    accounts_by_ref = {account["ref"]: account for account in explorer["accounts"]}
    program_address = explorer["program"]["address"]
    assert accounts_by_ref["pool_config"]["ownerProgram"] == program_address
    assert accounts_by_ref["pool_config"]["data"]["totalRewardsPaid"] == 14_325
    assert accounts_by_ref["stake_position"]["ownerProgram"] == program_address
    assert accounts_by_ref["stake_position"]["accountType"] == "StakePosition"
    assert accounts_by_ref["stake_position"]["data"]["pendingRewards"] == 12_500
    assert accounts_by_ref["pool_participant_1_wallet"]["accountType"] == "Wallet"
    assert accounts_by_ref["pool_participant_1_wallet"]["data"]["claimableRewards"] == 12_500
    assert accounts_by_ref["pool_participant_1_wallet"]["data"]["rewardSymbol"] == "USDC"
    assert accounts_by_ref["pool_participant_2_wallet"]["data"]["claimableRewards"] == 0
    assert accounts_by_ref["pool_participant_3_wallet"]["data"]["rewardSymbol"] == "STAKE"
    assert accounts_by_ref["user_reward_account"]["data"]["amount"] == 0
    assert accounts_by_ref["user_reward_account"]["data"]["claimableRewards"] == 250
    assert accounts_by_ref["reward_mint"]["data"]["symbol"] == "USDC"
    assert len(explorer["participants"]) == 5
    claimable_participants = [
        participant
        for participant in explorer["participants"]
        if participant["rewardSymbol"] == "USDC" and participant["claimableRewards"] > 0
    ]
    assert claimable_participants == [
        {
            "ref": "pool_participant_1_wallet",
            "label": "Pool Participant 1",
            "walletAddress": accounts_by_ref["stake_position"]["data"]["baselineOwner"],
            "positionRef": "stake_position",
            "positionAddress": accounts_by_ref["stake_position"]["address"],
            "stakeAmount": 50_000,
            "claimableRewards": 12_500,
            "rewardMintRef": "reward_mint",
            "rewardSymbol": "USDC",
            "status": "active_position",
        }
    ]
    assert explorer["rewardCandidates"] == [
        {
            "walletAddress": accounts_by_ref["stake_position"]["data"]["baselineOwner"],
            "positionAddress": accounts_by_ref["stake_position"]["address"],
            "positionRef": "stake_position",
            "positionLabel": "Staking Position",
            "pendingRewards": 12_500,
            "rewardMintRef": "reward_mint",
            "rewardSymbol": "USDC",
        }
    ]
    candidate = explorer["rewardCandidates"][0]
    assert accounts_by_ref[candidate["positionRef"]]["address"] == candidate["positionAddress"]
    assert "claimInstruction" not in candidate
    assert "recommendedAction" not in candidate
    assert "instructionName" not in candidate
    assert "instruction_name" not in candidate
    assert explorer["rewardAsset"] == {
        "mintRef": "reward_mint",
        "symbol": "USDC",
        "decimals": 6,
    }
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
    initial_candidate = initial_explorer["rewardCandidates"][0]
    decoy_wallet = next(
        participant
        for participant in initial_explorer["participants"]
        if participant["ref"] == "pool_participant_2_wallet"
    )["walletAddress"]
    attacker_wallet = next(
        account
        for account in initial_explorer["accounts"]
        if account["ref"] == "user_reward_account"
    )["data"]["owner"]

    own_claim = await _claim(seeded_client, headers, session_id, attacker_wallet)
    assert own_claim.status_code == 200
    own_claim_data = own_claim.json()["data"]
    assert own_claim_data["executionStatus"] == "success"
    assert own_claim_data["parameters"]["claim_scope"] == "own"
    assert own_claim_data["parameters"]["claimed_amount"] == 250
    own_claim_state = own_claim_data["protocolState"]
    assert own_claim_state["user"]["pendingRewards"] == 0
    assert own_claim_state["user"]["rewardBalance"] == 250
    assert own_claim_state["position"]["pendingRewards"] == 12_500
    assert own_claim_state["ownRewardsClaimedTotal"] == 250
    assert own_claim_state["exploitRewardsClaimedTotal"] == 0
    assert own_claim_state["pool"]["totalRewardsPaid"] == 14_575
    after_own_claim_explorer = (
        await seeded_client.get(
            f"/api/v1/research-labs/sessions/{session_id}/explorer",
            headers=headers,
        )
    ).json()["data"]
    assert after_own_claim_explorer["rewardCandidates"] == [initial_candidate]

    duplicate_own_claim = await _claim(seeded_client, headers, session_id, attacker_wallet)
    assert duplicate_own_claim.status_code == 200
    duplicate_own_claim_data = duplicate_own_claim.json()["data"]
    assert duplicate_own_claim_data["executionStatus"] == "failure"
    assert duplicate_own_claim_data["protocolState"]["lastRejectedReason"] == (
        "NO_REWARDS_AVAILABLE"
    )
    assert duplicate_own_claim_data["protocolState"]["position"]["pendingRewards"] == 12_500
    assert duplicate_own_claim_data["protocolState"]["user"]["rewardBalance"] == 250

    own_claim_verify = await seeded_client.post(
        f"/api/v1/research-labs/sessions/{session_id}/verify-objective", headers=headers
    )
    assert own_claim_verify.status_code == 200
    assert own_claim_verify.json()["data"]["impactVerified"] is False

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
    after_missing_instruction_explorer = (
        await seeded_client.get(
            f"/api/v1/research-labs/sessions/{session_id}/explorer",
            headers=headers,
        )
    ).json()["data"]
    assert after_missing_instruction_explorer["rewardCandidates"] == [initial_candidate]

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
    after_invalid_instruction_explorer = (
        await seeded_client.get(
            f"/api/v1/research-labs/sessions/{session_id}/explorer",
            headers=headers,
        )
    ).json()["data"]
    assert after_invalid_instruction_explorer["rewardCandidates"] == [initial_candidate]

    missing_target = await _claim(seeded_client, headers, session_id)
    assert missing_target.status_code == 200
    assert missing_target.json()["data"]["executionStatus"] == "failure"
    assert missing_target.json()["data"]["protocolState"]["lastRejectedReason"] == (
        "TARGET_WALLET_REQUIRED"
    )
    assert missing_target.json()["data"]["protocolState"]["position"]["pendingRewards"] == 12_500
    after_missing_target_explorer = (
        await seeded_client.get(
            f"/api/v1/research-labs/sessions/{session_id}/explorer",
            headers=headers,
        )
    ).json()["data"]
    assert after_missing_target_explorer["rewardCandidates"] == [initial_candidate]

    invalid_target = await _claim(
        seeded_client, headers, session_id, "11111111111111111111111111111111"
    )
    assert invalid_target.status_code == 200
    assert invalid_target.json()["data"]["executionStatus"] == "failure"
    assert invalid_target.json()["data"]["protocolState"]["lastRejectedReason"] == (
        "INVALID_TARGET_WALLET"
    )
    assert invalid_target.json()["data"]["protocolState"]["position"]["pendingRewards"] == 12_500
    after_invalid_target_explorer = (
        await seeded_client.get(
            f"/api/v1/research-labs/sessions/{session_id}/explorer",
            headers=headers,
        )
    ).json()["data"]
    assert after_invalid_target_explorer["rewardCandidates"] == [initial_candidate]

    decoy_target = await _claim(seeded_client, headers, session_id, decoy_wallet)
    assert decoy_target.status_code == 200
    assert decoy_target.json()["data"]["executionStatus"] == "failure"
    assert decoy_target.json()["data"]["protocolState"]["lastRejectedReason"] == (
        "INVALID_TARGET_WALLET"
    )
    after_decoy_target_explorer = (
        await seeded_client.get(
            f"/api/v1/research-labs/sessions/{session_id}/explorer",
            headers=headers,
        )
    ).json()["data"]
    assert after_decoy_target_explorer["rewardCandidates"] == [initial_candidate]

    early_claim = await _claim(seeded_client, headers, session_id, victim_wallet)
    assert early_claim.status_code == 200
    assert early_claim.json()["data"]["executionStatus"] == "failure"
    assert early_claim.json()["data"]["protocolState"]["lastRejectedReason"] == (
        "INVALID_POSITION_OWNER"
    )
    after_early_claim_explorer = (
        await seeded_client.get(
            f"/api/v1/research-labs/sessions/{session_id}/explorer",
            headers=headers,
        )
    ).json()["data"]
    assert after_early_claim_explorer["rewardCandidates"] == [initial_candidate]

    zero_stake = await _stake(seeded_client, headers, session_id, 0)
    assert zero_stake.status_code == 200
    assert zero_stake.json()["data"]["executionStatus"] == "failure"
    assert zero_stake.json()["data"]["protocolState"]["lastRejectedReason"] == "INVALID_AMOUNT"
    after_zero_stake_explorer = (
        await seeded_client.get(
            f"/api/v1/research-labs/sessions/{session_id}/explorer",
            headers=headers,
        )
    ).json()["data"]
    assert after_zero_stake_explorer["rewardCandidates"] == [initial_candidate]

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
    assert stake_state["position"]["owner"] == stake_state["user"]["wallet"]
    assert stake_state["position"]["stakedAmount"] == 50_001
    assert stake_state["position"]["pendingRewards"] == 12_500
    assert stake_state["user"]["positionStakedAmount"] == 1_001
    assert stake_state["pool"]["stakeVaultBalance"] == 50_001
    assert stake_state["pool"]["totalRewardsPaid"] == 14_575
    assert stake_state["totalRewardsPaid"] == 14_575
    assert stake_state["rewardsClaimedTotal"] == 250
    assert stake_state["ownRewardsClaimedTotal"] == 250
    assert stake_state["exploitRewardsClaimedTotal"] == 0
    assert stake_state["user"]["stakeBalance"] == 99

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
    assert after_stake_explorer["rewardCandidates"][0]["positionRef"] == "stake_position"
    assert after_stake_explorer["rewardCandidates"][0]["rewardSymbol"] == "USDC"
    assert after_stake_explorer["rewardCandidates"][0]["pendingRewards"] == 12_500

    claim = await _claim(seeded_client, headers, session_id, victim_wallet)
    assert claim.status_code == 200
    claim_data = claim.json()["data"]
    assert claim_data["executionStatus"] == "success"
    assert claim_data["parameters"]["instruction_name"] == "claim_rewards"
    claim_state = claim_data["protocolState"]
    assert claim_data["parameters"]["claim_scope"] == "exploit"
    assert claim_state["user"]["rewardBalance"] == 12_750
    assert claim_state["pool"]["rewardVaultBalance"] == 487_250
    assert claim_state["position"]["pendingRewards"] == 0
    assert claim_state["rewardsClaimedTotal"] == 12_750
    assert claim_state["ownRewardsClaimedTotal"] == 250
    assert claim_state["exploitRewardsClaimedTotal"] == 12_500
    assert claim_state["pool"]["totalRewardsPaid"] == 27_075
    assert claim_state["totalRewardsPaid"] == 27_075
    after_claim_explorer = (
        await seeded_client.get(
            f"/api/v1/research-labs/sessions/{session_id}/explorer",
            headers=headers,
        )
    ).json()["data"]
    assert after_claim_explorer["rewardCandidates"] == []
    assert after_claim_explorer["totalRewardsPaid"] == 27_075
    assert [
        participant
        for participant in after_claim_explorer["participants"]
        if participant["rewardSymbol"] == "USDC" and participant["claimableRewards"] > 0
    ] == []

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
    assert verified_data["evidence"]["impact"]["userStaked"] == 1
    assert verified_data["evidence"]["impact"]["rewardsClaimed"] == 12_500

    bad_review_answers = {
        **_correct_rl2_finding_review_answers(),
        "q1_vulnerability_category": "account_substitution",
    }
    bad_review = await seeded_client.post(
        f"/api/v1/research-labs/sessions/{session_id}/finding-review/submit",
        headers=headers,
        json={"answers": bad_review_answers},
    )
    assert bad_review.status_code == 200
    bad_review_data = bad_review.json()["data"]
    assert bad_review_data["findingReviewPassed"] is False
    assert bad_review_data["failedQuestionIds"] == ["q1_vulnerability_category"]

    good_review = await seeded_client.post(
        f"/api/v1/research-labs/sessions/{session_id}/finding-review/submit",
        headers=headers,
        json={"answers": _correct_rl2_finding_review_answers()},
    )
    assert good_review.status_code == 200
    good_review_data = good_review.json()["data"]
    assert good_review_data["status"] == "passed"
    assert good_review_data["findingReviewPassed"] is True
    assert good_review_data["failedQuestionIds"] == []

    report = await seeded_client.get(
        f"/api/v1/research-labs/sessions/{session_id}/report",
        headers=headers,
    )
    assert report.status_code == 200
    report_data = report.json()["data"]
    assert report_data["status"] == "draft"
    assert report_data["allowedValues"]["titleOptionId"][0]["id"] == (
        "static_staking_position_reward_hijack"
    )
    assert report_data["allowedValues"]["categoryOptionId"][0]["id"] == "static_pda"
    assert report_data["allowedValues"]["titleOptionId"][0]["id"] != (
        "missing_constraints_counterfeit_credit"
    )

    accepted_report_fields = _accepted_rl2_report_fields(verified_data["verifiedEvidenceRefs"])
    draft = await seeded_client.put(
        f"/api/v1/research-labs/sessions/{session_id}/report",
        headers=headers,
        json={"fields": accepted_report_fields},
    )
    assert draft.status_code == 200
    assert draft.json()["data"]["fields"]["titleOptionId"] == (
        "static_staking_position_reward_hijack"
    )

    accepted_report = await seeded_client.post(
        f"/api/v1/research-labs/sessions/{session_id}/report/submit",
        headers=headers,
    )
    assert accepted_report.status_code == 200
    accepted_report_data = accepted_report.json()["data"]
    assert accepted_report_data["status"] == "accepted"
    assert accepted_report_data["labCompleted"] is True
    assert accepted_report_data["certificateUnlockable"] is True
    assert accepted_report_data["fields"]["categoryOptionId"] == "static_pda"

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
