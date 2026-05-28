from httpx import AsyncClient


async def register_user(client: AsyncClient, email: str) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"username": email.split("@")[0], "email": email, "password": "strong-password"},
    )
    assert response.status_code == 201


async def login_token(client: AsyncClient, email: str) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "strong-password"},
    )
    assert response.status_code == 200
    return response.json()["tokens"]["access_token"]


async def test_treasury_mirage_research_lab_full_backend_flow(
    seeded_client: AsyncClient,
) -> None:
    await register_user(seeded_client, email="researcher@example.com")
    token = await login_token(seeded_client, email="researcher@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    catalog_response = await seeded_client.get("/api/v1/research-labs", headers=headers)
    assert catalog_response.status_code == 200
    catalog = catalog_response.json()
    assert catalog["success"] is True
    assert catalog["data"][0]["id"] == "rl-001"
    assert catalog["data"][0]["slug"] == "treasury-mirage"
    assert "test_command" not in catalog["data"][0]

    detail_response = await seeded_client.get("/api/v1/research-labs/rl-001", headers=headers)
    assert detail_response.status_code == 200
    detail = detail_response.json()["data"]
    assert detail["entry_file"] == "programs/treasury_mirage/src/lib.rs"
    assert detail["scenario_briefing"]

    create_response = await seeded_client.post(
        "/api/v1/research-labs/rl-001/sessions", headers=headers
    )
    assert create_response.status_code == 201
    session_data = create_response.json()["data"]
    session_id = session_data["session_id"]
    assert session_data["status"] == "active"
    assert session_data["phase"] == "INSPECT"
    assert session_data["sandboxStatus"] == "READY"
    assert session_data["reportUnlocked"] is False
    assert session_data["allowed_files"] == ["programs/treasury_mirage/src/lib.rs"]
    assert session_data["files"][0]["writable"] is False
    assert "deposit_collateral" in session_data["files"][0]["content"]
    assert session_data["terminal"][0]["sequence"] == 1

    patch_attempt = await seeded_client.patch(
        f"/api/v1/research-labs/sessions/{session_id}/files",
        headers=headers,
        json={
            "files": [
                {
                    "path": "programs/treasury_mirage/src/lib.rs",
                    "content": "bad",
                }
            ]
        },
    )
    assert patch_attempt.status_code == 403

    accounts_response = await seeded_client.get(
        f"/api/v1/research-labs/sessions/{session_id}/accounts", headers=headers
    )
    assert accounts_response.status_code == 200
    accounts = accounts_response.json()["data"]["accounts"]
    assert {account["ref"] for account in accounts} >= {
        "treasury_vault",
        "attacker_collateral_account",
        "attacker_reward_account",
    }

    account_response = await seeded_client.get(
        f"/api/v1/research-labs/sessions/{session_id}/accounts/attacker_collateral_account",
        headers=headers,
    )
    assert account_response.status_code == 200
    account_data = account_response.json()["data"]["account"]["data"]
    assert "mint" in account_data, "Token account data must include mint field"
    assert "amount" in account_data, "Token account data must include amount"
    assert int(account_data["amount"]) == 500000, f"Expected 500000 counterfeit tokens, got {account_data['amount']}"

    locked_report_response = await seeded_client.get(
        f"/api/v1/research-labs/sessions/{session_id}/report", headers=headers
    )
    assert locked_report_response.status_code == 200
    assert locked_report_response.json()["data"]["status"] == "locked"

    premature_submit_response = await seeded_client.post(
        f"/api/v1/research-labs/sessions/{session_id}/report/submit", headers=headers
    )
    assert premature_submit_response.status_code == 409

    premature_verify = await seeded_client.post(
        f"/api/v1/research-labs/sessions/{session_id}/verify-objective",
        headers=headers,
    )
    assert premature_verify.status_code == 200
    assert premature_verify.json()["data"]["passed"] is False

    deposit_response = await seeded_client.post(
        f"/api/v1/research-labs/sessions/{session_id}/transactions",
        headers=headers,
        json={
            "action_type": "DEPOSIT_COLLATERAL",
            "parameters": {
                "amount": 50000,
                "collateral_account_ref": "attacker_collateral_account",
                "vault_account_ref": "counterfeit_vault_account",
            },
        },
    )
    assert deposit_response.status_code == 200
    assert deposit_response.json()["data"]["execution_status"] == "success"

    withdraw_response = await seeded_client.post(
        f"/api/v1/research-labs/sessions/{session_id}/transactions",
        headers=headers,
        json={"action_type": "WITHDRAW_AGAINST_CREDIT", "parameters": {"amount": 50000}},
    )
    assert withdraw_response.status_code == 200
    transaction_ref = withdraw_response.json()["data"]["transaction_ref"]

    logs_response = await seeded_client.get(
        f"/api/v1/research-labs/sessions/{session_id}/transactions/{transaction_ref}/logs",
        headers=headers,
    )
    assert logs_response.status_code == 200
    logs = logs_response.json()["data"]["logs"]
    assert len(logs) > 0, "LiteSVM must produce execution logs"
    assert any("Program" in line for line in logs), "Logs must contain SVM program trace"

    verify_response = await seeded_client.post(
        f"/api/v1/research-labs/sessions/{session_id}/verify-objective",
        headers=headers,
    )
    assert verify_response.status_code == 200
    verified = verify_response.json()["data"]
    assert verified["passed"] is True
    assert verified["phase"] == "REPORT"
    assert verified["reportUnlocked"] is True

    draft_report_response = await seeded_client.get(
        f"/api/v1/research-labs/sessions/{session_id}/report", headers=headers
    )
    assert draft_report_response.status_code == 200
    draft_report = draft_report_response.json()["data"]
    assert draft_report["status"] == "draft"
    assert draft_report["fields"]["vulnerability_category"] is None
    assert draft_report["allowed_values"]["severity"] == ["low", "medium", "high"]

    bad_report_response = await seeded_client.put(
        f"/api/v1/research-labs/sessions/{session_id}/report",
        headers=headers,
        json={
            "fields": {
                "vulnerability_category": "missing_validation",
                "affected_area": "deposit_instruction",
                "attacker_controlled_input": "collateral_token_account",
                "root_cause": "The wrong thing is checked.",
                "impact": "The issue can cause bad accounting.",
                "proof": "The tests pass after a code patch.",
                "recommended_fix": "Add a validation check.",
                "severity": "low",
            }
        },
    )
    assert bad_report_response.status_code == 200
    retry_response = await seeded_client.post(
        f"/api/v1/research-labs/sessions/{session_id}/report/submit", headers=headers
    )
    assert retry_response.status_code == 200
    retry = retry_response.json()["data"]
    assert retry["status"] == "retry"
    assert retry["lab_completed"] is False
    assert retry["xp_awarded"] == 0

    accepted_report_response = await seeded_client.put(
        f"/api/v1/research-labs/sessions/{session_id}/report",
        headers=headers,
        json={
            "fields": {
                "vulnerability_category": "missing_validation",
                "affected_area": "deposit_instruction",
                "attacker_controlled_input": "collateral_token_account",
                "root_cause": (
                    "The deposit instruction has missing validation for the collateral token "
                    "account mint."
                ),
                "impact": (
                    "An attacker can deposit counterfeit tokens, receive credit, and withdraw "
                    "treasury value."
                ),
                "proof": "The sandbox evidence shows counterfeit collateral was credited.",
                "recommended_fix": (
                    "Require the token account mint to equal the accepted official mint before "
                    "crediting deposits."
                ),
                "severity": "medium",
            }
        },
    )
    assert accepted_report_response.status_code == 200
    accepted_response = await seeded_client.post(
        f"/api/v1/research-labs/sessions/{session_id}/report/submit", headers=headers
    )
    assert accepted_response.status_code == 200
    accepted = accepted_response.json()["data"]
    assert accepted["status"] == "accepted"
    assert accepted["lab_completed"] is True
    assert accepted["xp_awarded"] == 250

    completed_session_response = await seeded_client.get(
        f"/api/v1/research-labs/sessions/{session_id}", headers=headers
    )
    assert completed_session_response.status_code == 200
    assert completed_session_response.json()["data"]["phase"] == "COMPLETED"

    me_response = await seeded_client.get("/api/v1/auth/me", headers=headers)
    assert me_response.json()["xp"] == 250
    assert me_response.json()["completed_levels"] == 0


async def test_research_lab_session_ownership_is_enforced(seeded_client: AsyncClient) -> None:
    await register_user(seeded_client, email="owner@example.com")
    owner_token = await login_token(seeded_client, email="owner@example.com")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    create_response = await seeded_client.post(
        "/api/v1/research-labs/treasury-mirage/sessions", headers=owner_headers
    )
    session_id = create_response.json()["data"]["session_id"]

    await register_user(seeded_client, email="intruder@example.com")
    intruder_token = await login_token(seeded_client, email="intruder@example.com")
    intruder_headers = {"Authorization": f"Bearer {intruder_token}"}

    response = await seeded_client.get(
        f"/api/v1/research-labs/sessions/{session_id}", headers=intruder_headers
    )
    assert response.status_code == 403
