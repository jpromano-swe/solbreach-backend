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


async def _create_rl3_session(client: AsyncClient, headers: dict[str, str]) -> str:
    response = await client.post("/api/v1/research-labs/rl3-arbitrary-cpi/sessions", headers=headers)
    assert response.status_code == 201
    return response.json()["data"]["session_id"]


async def _build_attacker_program(client: AsyncClient, headers: dict[str, str], session_id: str):
    return await client.post(
        f"/api/v1/research-labs/sessions/{session_id}/transactions",
        headers=headers,
        json={
            "action_type": "BUILD_ATTACKER_PROGRAM",
            "parameters": {
                "task_ref": "design_ops_console",
                "category_ref": "design",
                "program_template": "cpi_drain_router",
                "entrypoint_name": "execute",
                "transfer_function": "transfer_checked",
                "transfer_source_ref": "task_escrow",
                "transfer_destination_ref": "attacker_reward_account",
                "authority_strategy": "reuse_delegated_signer",
            },
        },
    )


async def _deploy_attacker_program(client: AsyncClient, headers: dict[str, str], session_id: str):
    return await client.post(
        f"/api/v1/research-labs/sessions/{session_id}/transactions",
        headers=headers,
        json={
            "action_type": "DEPLOY_ATTACKER_PROGRAM",
            "parameters": {"artifact_ref": "attacker_program_build"},
        },
    )


async def _submit_delegation(client: AsyncClient, headers: dict[str, str], session_id: str):
    return await client.post(
        f"/api/v1/research-labs/sessions/{session_id}/transactions",
        headers=headers,
        json={
            "action_type": "SUBMIT_DELEGATION",
            "parameters": {
                "task_ref": "design_ops_console",
                "delegate_program_ref": "official_payout_router",
                "reward_amount": 750,
            },
        },
    )


async def _execute_cpi(
    client: AsyncClient,
    headers: dict[str, str],
    session_id: str,
    *,
    instruction_name: str | None = "execute",
    delegate_program_ref: str = "attacker_cpi_program",
    task_ref: str = "design_ops_console",
    amount: int = 750,
):
    parameters = {
        "task_ref": task_ref,
        "delegate_program_ref": delegate_program_ref,
        "destination_account_ref": "attacker_reward_account",
        "amount": amount,
    }
    if instruction_name is not None:
        parameters["instruction_name"] = instruction_name
    return await client.post(
        f"/api/v1/research-labs/sessions/{session_id}/transactions",
        headers=headers,
        json={"action_type": "EXECUTE_DELEGATED_CPI", "parameters": parameters},
    )


def _correct_rl3_finding_review_answers() -> dict[str, str]:
    return {
        "q1_vulnerability_category": "arbitrary_cpi_target",
        "q2_public_instruction": "execute_delegated_payout",
        "q3_exploit_sequence": "build_deploy_delegate_execute_attacker_cpi",
        "q4_deployment_scope": "session_scoped_sandbox_program",
        "q5_impact": "task_escrow_drained_to_attacker_reward_account",
        "q6_evidence": "attacker_program_deployed,cpi_target_replaced,escrow_delta_matches",
        "q7_severity": "high",
        "q8_recommended_fix": "bind_cpi_target_to_approved_router",
    }


def _accepted_rl3_report_fields(verified_evidence_refs: list[str]) -> dict:
    return {
        "titleOptionId": "arbitrary_cpi_target_bounty_drain",
        "severityOptionId": "high",
        "likelihoodOptionId": "high",
        "categoryOptionId": "arbitrary_cpi",
        "rootCauseOptionId": "unbound_cpi_program_target",
        "proofOfImpactOptionId": "attacker_cpi_drains_task_escrow",
        "recommendedMitigationOptionId": "bind_cpi_target_to_approved_router",
        "verifiedEvidenceRefs": verified_evidence_refs,
        "optionalNotes": "Verified arbitrary CPI target replacement.",
    }


async def test_rl3_task_scope_rejects_invalid_and_v2_paths(
    seeded_client: AsyncClient,
) -> None:
    await _register_user(seeded_client, "rl3-contract@example.com")
    token = await _login_token(seeded_client, "rl3-contract@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    session_id = await _create_rl3_session(seeded_client, headers)

    deploy_without_artifact = await _deploy_attacker_program(seeded_client, headers, session_id)
    assert deploy_without_artifact.status_code == 200
    assert deploy_without_artifact.json()["data"]["executionStatus"] == "failure"
    assert deploy_without_artifact.json()["data"]["protocolState"]["lastRejectedReason"] == (
        "ATTACKER_PROGRAM_NOT_BUILT"
    )

    bad_category = await seeded_client.post(
        f"/api/v1/research-labs/sessions/{session_id}/transactions",
        headers=headers,
        json={
            "action_type": "BUILD_ATTACKER_PROGRAM",
            "parameters": {
                "task_ref": "design_ops_console",
                "category_ref": "development",
                "program_template": "cpi_drain_router",
                "entrypoint_name": "execute",
                "transfer_function": "transfer_checked",
                "transfer_source_ref": "task_escrow",
                "transfer_destination_ref": "attacker_reward_account",
                "authority_strategy": "reuse_delegated_signer",
            },
        },
    )
    assert bad_category.status_code == 200
    assert bad_category.json()["data"]["executionStatus"] == "failure"
    assert bad_category.json()["data"]["protocolState"]["lastRejectedReason"] == (
        "TASK_CATEGORY_MISMATCH"
    )

    v2_build = await seeded_client.post(
        f"/api/v1/research-labs/sessions/{session_id}/transactions",
        headers=headers,
        json={
            "action_type": "BUILD_ATTACKER_PROGRAM",
            "parameters": {
                "task_ref": "development_secure_worker",
                "category_ref": "development",
                "program_template": "cpi_drain_router",
                "entrypoint_name": "execute",
                "transfer_function": "transfer_checked",
                "transfer_source_ref": "task_escrow",
                "transfer_destination_ref": "attacker_reward_account",
                "authority_strategy": "reuse_delegated_signer",
            },
        },
    )
    assert v2_build.status_code == 200
    assert v2_build.json()["data"]["executionStatus"] == "failure"
    assert v2_build.json()["data"]["protocolState"]["lastRejectedReason"] == (
        "TASK_TARGET_BINDING_ENFORCED"
    )

    build = await _build_attacker_program(seeded_client, headers, session_id)
    assert build.json()["data"]["executionStatus"] == "success"
    deploy = await _deploy_attacker_program(seeded_client, headers, session_id)
    assert deploy.json()["data"]["executionStatus"] == "success"

    mismatched_router = await seeded_client.post(
        f"/api/v1/research-labs/sessions/{session_id}/transactions",
        headers=headers,
        json={
            "action_type": "SUBMIT_DELEGATION",
            "parameters": {
                "task_ref": "design_ops_console",
                "delegate_program_ref": "attacker_cpi_program",
                "reward_amount": 750,
            },
        },
    )
    assert mismatched_router.status_code == 200
    assert mismatched_router.json()["data"]["executionStatus"] == "failure"
    assert mismatched_router.json()["data"]["protocolState"]["lastRejectedReason"] == (
        "INVALID_DELEGATION_ROUTER"
    )

    mismatched_amount = await seeded_client.post(
        f"/api/v1/research-labs/sessions/{session_id}/transactions",
        headers=headers,
        json={
            "action_type": "SUBMIT_DELEGATION",
            "parameters": {
                "task_ref": "design_ops_console",
                "delegate_program_ref": "official_payout_router",
                "reward_amount": 749,
            },
        },
    )
    assert mismatched_amount.status_code == 200
    assert mismatched_amount.json()["data"]["executionStatus"] == "failure"
    assert mismatched_amount.json()["data"]["protocolState"]["lastRejectedReason"] == (
        "INVALID_REWARD_AMOUNT"
    )

    delegation = await _submit_delegation(seeded_client, headers, session_id)
    assert delegation.json()["data"]["executionStatus"] == "success"

    v2_cpi = await _execute_cpi(
        seeded_client,
        headers,
        session_id,
        task_ref="development_secure_worker",
        amount=1_200,
    )
    assert v2_cpi.status_code == 200
    assert v2_cpi.json()["data"]["executionStatus"] == "failure"
    assert v2_cpi.json()["data"]["protocolState"]["lastRejectedReason"] == (
        "CPI_TARGET_BINDING_ENFORCED"
    )

    over_drain = await _execute_cpi(seeded_client, headers, session_id, amount=3_000)
    assert over_drain.status_code == 200
    assert over_drain.json()["data"]["executionStatus"] == "failure"
    assert over_drain.json()["data"]["protocolState"]["lastRejectedReason"] == (
        "INVALID_DRAIN_AMOUNT"
    )

    legacy_cpi = await _execute_cpi(
        seeded_client,
        headers,
        session_id,
        instruction_name="execute_delegated_payout",
        task_ref="task_record",
    )
    assert legacy_cpi.status_code == 200
    assert legacy_cpi.json()["data"]["executionStatus"] == "success"
    assert legacy_cpi.json()["data"]["parameters"]["task_ref"] == "design_ops_console"
    assert legacy_cpi.json()["data"]["parameters"]["instruction_name"] == "execute"


async def test_rl3_arbitrary_cpi_full_backend_flow(seeded_client: AsyncClient) -> None:
    await _register_user(seeded_client, "rl3-flow@example.com")
    token = await _login_token(seeded_client, "rl3-flow@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    catalog = (await seeded_client.get("/api/v1/research-labs", headers=headers)).json()["data"]
    assert any(lab["id"] == "rl3-arbitrary-cpi" for lab in catalog)
    session_id = await _create_rl3_session(seeded_client, headers)
    session_response = await seeded_client.get(
        f"/api/v1/research-labs/sessions/{session_id}",
        headers=headers,
    )
    assert session_response.status_code == 200
    assert session_response.json()["data"]["wallet"] == {
        "wallet_address": None,
        "walletAddress": None,
        "display_name": "rl3-flow",
        "displayName": "rl3-flow",
        "avatar_url": None,
        "avatarUrl": None,
        "available_usdc": 0,
        "availableUsdc": 0,
    }

    explorer_response = await seeded_client.get(
        f"/api/v1/research-labs/sessions/{session_id}/explorer",
        headers=headers,
    )
    assert explorer_response.status_code == 200
    explorer = explorer_response.json()["data"]
    assert explorer["network"] == {"name": "SolBreach SVM", "kind": "sandbox"}
    assert explorer["program"]["ref"] == "task_bounty"
    assert {instruction["name"] for instruction in explorer["program"]["idl"]["instructions"]} == {
        "create_task",
        "fund_task",
        "delegate_payout",
        "execute",
        "execute_delegated_payout",
    }
    account_refs = {account["ref"] for account in explorer["accounts"]}
    assert account_refs == {
        "bounty_config",
        "bounty_authority",
        "bounty_vault",
        "task_record",
        "task_escrow",
        "official_payout_router",
        "approved_worker_account",
        "attacker_reward_account",
        "attacker_program_buffer",
    }
    assert "protocol_guard_state" not in account_refs
    assert "internal_bounty_ledger" not in account_refs
    assert "answer_key" not in account_refs
    assert "attacker_cpi_program" not in account_refs
    assert explorer["protocolState"]["bountyPool"]["availableLiquidity"] == 3_000
    assert explorer["protocolState"]["attackerProgram"]["deployed"] is False
    assert explorer["protocolState"]["selectedTask"]["taskRef"] == "design_ops_console"
    assert explorer["protocolState"]["selectedTask"]["payoutConfigVersion"] == "V1"
    assert explorer["protocolState"]["selectedTask"]["targetBindingEnforced"] is False
    assert {category["category_ref"] for category in explorer["protocolState"]["categories"]} == {
        "design",
        "development",
        "content",
        "memes",
    }
    assert {
        task["taskRef"]
        for task in explorer["protocolState"]["tasks"]
        if task["targetBindingEnforced"]
    } == {
        "development_secure_worker",
        "content_security_brief",
        "memes_campaign_assets",
        "payout_review_plugin",
    }

    scope_response = await seeded_client.get(
        f"/api/v1/research-labs/sessions/{session_id}/scope",
        headers=headers,
    )
    assert scope_response.status_code == 200
    scope = scope_response.json()["data"]
    assert scope["wallet"]["display_name"] == "rl3-flow"
    assert scope["wallet"]["available_usdc"] == 0
    assert scope["selectedTask"]["taskRef"] == "design_ops_console"
    assert scope["currentOpportunity"]["taskRef"] == "design_ops_console"
    assert scope["currentScope"]["taskRef"] == "design_ops_console"
    assert scope["tasks"][0]["payoutConfigRef"] == "design_payout_config_v1"

    early_cpi = await _execute_cpi(seeded_client, headers, session_id)
    assert early_cpi.status_code == 200
    early_cpi_data = early_cpi.json()["data"]
    assert early_cpi_data["executionStatus"] == "failure"
    assert early_cpi_data["protocolState"]["lastRejectedReason"] == "DELEGATION_REQUIRED"
    assert early_cpi_data["protocolState"]["bountyPool"]["availableLiquidity"] == 3_000
    assert early_cpi_data["protocolState"]["attacker"]["rewardBalance"] == 0

    missing_instruction = await _execute_cpi(
        seeded_client, headers, session_id, instruction_name=None
    )
    assert missing_instruction.status_code == 200
    assert missing_instruction.json()["data"]["executionStatus"] == "failure"
    assert missing_instruction.json()["data"]["protocolState"]["lastRejectedReason"] == (
        "INSTRUCTION_NAME_REQUIRED"
    )

    invalid_instruction = await _execute_cpi(
        seeded_client, headers, session_id, instruction_name="executeDelegatedPayout"
    )
    assert invalid_instruction.status_code == 200
    assert invalid_instruction.json()["data"]["executionStatus"] == "failure"
    assert invalid_instruction.json()["data"]["protocolState"]["lastRejectedReason"] == (
        "INVALID_INSTRUCTION_NAME"
    )

    bad_build = await seeded_client.post(
        f"/api/v1/research-labs/sessions/{session_id}/transactions",
        headers=headers,
        json={
            "action_type": "BUILD_ATTACKER_PROGRAM",
            "parameters": {
                "task_ref": "design_ops_console",
                "category_ref": "design",
                "program_template": "raw_user_code",
                "entrypoint_name": "execute",
                "transfer_function": "transfer_checked",
                "transfer_source_ref": "task_escrow",
                "transfer_destination_ref": "attacker_reward_account",
                "authority_strategy": "reuse_delegated_signer",
            },
        },
    )
    assert bad_build.status_code == 200
    assert bad_build.json()["data"]["executionStatus"] == "failure"
    assert bad_build.json()["data"]["protocolState"]["lastRejectedReason"] == (
        "INVALID_PROGRAM_TEMPLATE"
    )

    build = await _build_attacker_program(seeded_client, headers, session_id)
    assert build.status_code == 200
    build_data = build.json()["data"]
    assert build_data["executionStatus"] == "success"
    assert build_data["parameters"]["artifact_ref"] == "attacker_program_build"
    assert build_data["parameters"]["task_ref"] == "design_ops_console"
    assert build_data["parameters"]["category_ref"] == "design"
    assert build_data["parameters"]["transfer_function"] == "transfer_checked"
    assert build_data["parameters"]["compile_status"] == "success"
    assert build_data["parameters"]["build_spec"]["task_ref"] == "design_ops_console"
    assert build_data["userFacingEvidence"][0]["wallet"]["display_name"] == "rl3-flow"
    assert build_data["userFacingEvidence"][0]["wallet"]["available_usdc"] == 0
    assert build_data["userFacingEvidence"][0]["task"]["taskRef"] == "design_ops_console"
    assert build_data["userFacingEvidence"][0]["currentOpportunity"]["taskRef"] == (
        "design_ops_console"
    )
    assert build_data["userFacingEvidence"][0]["payoutConfig"] == {
        "ref": "design_payout_config_v1",
        "version": "V1",
        "targetBindingEnforced": False,
    }
    assert build_data["userFacingEvidence"][0]["evidenceRefs"] == [
        "artifact:attacker_program_build"
    ]
    assert build_data["protocolState"]["attackerProgram"]["built"] is True
    assert build_data["protocolState"]["attackerProgram"]["deployed"] is False

    deploy = await _deploy_attacker_program(seeded_client, headers, session_id)
    assert deploy.status_code == 200
    deploy_data = deploy.json()["data"]
    assert deploy_data["executionStatus"] == "success"
    assert deploy_data["parameters"]["program_ref"] == "attacker_cpi_program"
    assert deploy_data["parameters"]["program_address"]
    assert deploy_data["protocolState"]["attackerProgram"]["deployed"] is True
    assert deploy_data["protocolState"]["bountyPool"]["availableLiquidity"] == 3_000

    after_deploy_explorer = (
        await seeded_client.get(
            f"/api/v1/research-labs/sessions/{session_id}/explorer",
            headers=headers,
        )
    ).json()["data"]
    after_deploy_refs = {account["ref"] for account in after_deploy_explorer["accounts"]}
    assert "attacker_cpi_program" in after_deploy_refs
    attacker_program_account = next(
        account
        for account in after_deploy_explorer["accounts"]
        if account["ref"] == "attacker_cpi_program"
    )
    assert attacker_program_account["data"]["sessionScoped"] is True

    delegation = await _submit_delegation(seeded_client, headers, session_id)
    assert delegation.status_code == 200
    delegation_data = delegation.json()["data"]
    assert delegation_data["executionStatus"] == "success"
    assert delegation_data["protocolState"]["user"]["normalDelegationSubmitted"] is True

    official_target = await _execute_cpi(
        seeded_client,
        headers,
        session_id,
        delegate_program_ref="official_payout_router",
    )
    assert official_target.status_code == 200
    assert official_target.json()["data"]["executionStatus"] == "failure"
    assert official_target.json()["data"]["protocolState"]["lastRejectedReason"] == (
        "OFFICIAL_ROUTER_TARGET_REJECTED"
    )
    assert official_target.json()["data"]["protocolState"]["task"]["escrowBalance"] == 750

    cpi = await _execute_cpi(seeded_client, headers, session_id)
    assert cpi.status_code == 200
    cpi_data = cpi.json()["data"]
    assert cpi_data["executionStatus"] == "success"
    assert cpi_data["parameters"]["instruction_name"] == "execute"
    assert cpi_data["parameters"]["delegate_program_ref"] == "attacker_cpi_program"
    state = cpi_data["protocolState"]
    assert state["bountyPool"] == {
        "totalEscrowed": 3_000,
        "availableLiquidity": 2_250,
        "paidOut": 750,
    }
    assert state["task"]["status"] == "paid"
    assert state["task"]["escrowBalance"] == 0
    assert state["attacker"]["rewardBalance"] == 750
    assert state["wallet"]["available_usdc"] == 750
    assert cpi_data["userFacingEvidence"][0]["wallet"]["available_usdc"] == 750
    assert cpi_data["userFacingEvidence"][0]["instructionName"] == "execute"
    assert state["cpi"]["targetReplaced"] is True

    post_cpi_scope = (
        await seeded_client.get(
            f"/api/v1/research-labs/sessions/{session_id}/scope",
            headers=headers,
        )
    ).json()["data"]
    assert post_cpi_scope["wallet"]["available_usdc"] == 750

    verified = await seeded_client.post(
        f"/api/v1/research-labs/sessions/{session_id}/verify-objective",
        headers=headers,
    )
    assert verified.status_code == 200
    verified_data = verified.json()["data"]
    assert verified_data["impactVerified"] is True
    assert verified_data["evidence"]["vulnerabilityClass"] == "ARBITRARY_CPI"
    assert verified_data["evidence"]["impactChecklist"]["attackerProgramDeployed"] is True
    assert verified_data["evidence"]["impactChecklist"]["officialRouterBypassed"] is True
    assert "transaction:" in verified_data["verifiedEvidenceRefs"][0]

    review = await seeded_client.post(
        f"/api/v1/research-labs/sessions/{session_id}/finding-review/submit",
        headers=headers,
        json={"answers": _correct_rl3_finding_review_answers()},
    )
    assert review.status_code == 200
    assert review.json()["data"]["findingReviewPassed"] is True

    report = await seeded_client.get(
        f"/api/v1/research-labs/sessions/{session_id}/report",
        headers=headers,
    )
    assert report.status_code == 200
    assert report.json()["data"]["allowedValues"]["categoryOptionId"][0]["id"] == "arbitrary_cpi"

    draft = await seeded_client.put(
        f"/api/v1/research-labs/sessions/{session_id}/report",
        headers=headers,
        json={"fields": _accepted_rl3_report_fields(verified_data["verifiedEvidenceRefs"])},
    )
    assert draft.status_code == 200
    accepted = await seeded_client.post(
        f"/api/v1/research-labs/sessions/{session_id}/report/submit",
        headers=headers,
    )
    assert accepted.status_code == 200
    accepted_data = accepted.json()["data"]
    assert accepted_data["status"] == "accepted"
    assert accepted_data["labCompleted"] is True
    assert accepted_data["certificateUnlockable"] is True
