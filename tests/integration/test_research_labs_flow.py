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


def _correct_finding_review_answers() -> dict[str, str]:
    return {
        "q1_vulnerability_category": "account_substitution",
        "q2_invalid_inputs": "candidate_collateral_and_external_vault",
        "q3_credit_origin": "invalid_account_relationship_created_credit",
        "q4_exploit_sequence": "invalid_deposit_then_treasury_withdrawal",
        "q5_treasury_impact": "real_protocol_value_left_treasury",
        "q6_impact_proven": "only_after_invalid_credit_enables_real_withdrawal",
        "q7_evidence_source": "transaction_and_account_evidence",
        "q8_recommended_fix": "bind_accounts_to_approved_config",
    }


def _accepted_report_fields(verified_evidence_refs: list[str]) -> dict:
    return {
        "titleOptionId": "missing_constraints_counterfeit_credit",
        "severityOptionId": "high_treasury_loss",
        "likelihoodOptionId": "medium_high_attacker_supplied_accounts",
        "categoryOptionId": "account_substitution",
        "rootCauseOptionId": "missing_account_binding",
        "proofOfImpactOptionId": "counterfeit_credit_withdraws_treasury",
        "recommendedMitigationOptionId": "bind_accounts_to_approved_config",
        "verifiedEvidenceRefs": verified_evidence_refs,
        "optionalNotes": "Backend-verified impact confirms invalid account binding.",
    }


EXPLOIT_MAX_BORROW = 400_000
OFFICIAL_MAX_BORROW = 40_000


async def test_rl1_account_substitution_full_backend_flow(
    seeded_client: AsyncClient,
) -> None:
    await register_user(seeded_client, email="researcher@example.com")
    token = await login_token(seeded_client, email="researcher@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    catalog_response = await seeded_client.get("/api/v1/research-labs", headers=headers)
    assert catalog_response.status_code == 200
    catalog = catalog_response.json()
    assert catalog["success"] is True
    assert catalog["data"][0]["id"] == "rl1-account-substitution"
    assert catalog["data"][0]["slug"] == "account-substitution"
    assert catalog["data"][0]["title"] == "Account Substitution"
    assert "Treasury Mirage" not in catalog["data"][0]["title"]

    detail_response = await seeded_client.get(
        "/api/v1/research-labs/rl1-account-substitution", headers=headers
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()["data"]
    assert detail["entry_file"] == "programs/treasury_mirage/src/lib.rs"
    assert "account binding" in detail["objective"].lower()

    create_response = await seeded_client.post(
        "/api/v1/research-labs/rl1-account-substitution/sessions", headers=headers
    )
    assert create_response.status_code == 201
    session_data = create_response.json()["data"]
    session_id = session_data["session_id"]
    assert session_data["status"] == "active"
    assert session_data["phase"] == "INSPECT"
    assert session_data["impactVerified"] is False
    assert session_data["reportUnlocked"] is False
    assert session_data["reportStatus"] == "locked"
    assert session_data["certificateUnlockable"] is False

    locked_finding_response = await seeded_client.get(
        f"/api/v1/research-labs/sessions/{session_id}/finding-review", headers=headers
    )
    assert locked_finding_response.status_code == 200
    assert locked_finding_response.json()["data"]["status"] == "locked"

    locked_report_response = await seeded_client.get(
        f"/api/v1/research-labs/sessions/{session_id}/report", headers=headers
    )
    assert locked_report_response.status_code == 200
    assert locked_report_response.json()["data"]["status"] == "locked"

    premature_verify = await seeded_client.post(
        f"/api/v1/research-labs/sessions/{session_id}/verify-objective",
        headers=headers,
    )
    assert premature_verify.status_code == 200
    assert premature_verify.json()["data"]["passed"] is False
    assert premature_verify.json()["data"]["impactVerified"] is False

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
    deposit_data = deposit_response.json()["data"]
    assert deposit_data["execution_status"] == "success"
    assert deposit_data["accountDeltas"]
    assert deposit_data["evidenceRefs"] == [f"transaction:{deposit_data['transaction_ref']}"]
    assert deposit_data["protocolState"]["depositPathType"] == "exploit"
    assert deposit_data["protocolState"]["creditedCollateral"] == 500_000
    assert deposit_data["protocolState"]["maxBorrow"] == EXPLOIT_MAX_BORROW

    withdraw_response = await seeded_client.post(
        f"/api/v1/research-labs/sessions/{session_id}/transactions",
        headers=headers,
        json={"action_type": "WITHDRAW_AGAINST_CREDIT", "parameters": {"amount": EXPLOIT_MAX_BORROW}},
    )
    assert withdraw_response.status_code == 200
    withdraw_data = withdraw_response.json()["data"]
    assert withdraw_data["execution_status"] == "success"
    assert withdraw_data["protocolState"]["borrowedTotal"] == EXPLOIT_MAX_BORROW
    assert withdraw_data["protocolState"]["availableBorrow"] == 0

    verify_response = await seeded_client.post(
        f"/api/v1/research-labs/sessions/{session_id}/verify-objective",
        headers=headers,
    )
    assert verify_response.status_code == 200
    verified = verify_response.json()["data"]
    assert verified["passed"] is True
    assert verified["impactVerified"] is True
    assert verified["reportUnlocked"] is True
    assert verified["certificateUnlockable"] is False
    assert verified["phase"] == "SUBMIT_FINDING"
    assert len(verified["verifiedEvidenceRefs"]) >= 3
    assert verified["evidence"]["impactChecklist"]["counterfeitDepositObserved"] is True
    assert verified["evidence"]["impactChecklist"]["realProtocolTreasuryValueDecreased"] is True
    assert verified["evidence"]["impactChecklist"]["maxDrainSatisfied"] is True
    assert verified["evidence"]["borrowedAmount"] == EXPLOIT_MAX_BORROW

    draft_report_response = await seeded_client.get(
        f"/api/v1/research-labs/sessions/{session_id}/report", headers=headers
    )
    assert draft_report_response.status_code == 200
    draft_report = draft_report_response.json()["data"]
    assert draft_report["status"] == "draft"
    assert draft_report["verifiedEvidenceRefs"] == verified["verifiedEvidenceRefs"]
    assert draft_report["fields"]["titleOptionId"] is None

    bad_finding_response = await seeded_client.post(
        f"/api/v1/research-labs/sessions/{session_id}/finding-review/submit",
        headers=headers,
        json={"answers": {"q1_vulnerability_category": "oracle_manipulation"}},
    )
    assert bad_finding_response.status_code == 200
    assert bad_finding_response.json()["data"]["status"] == "retry"
    assert bad_finding_response.json()["data"]["findingReviewPassed"] is False

    good_finding_response = await seeded_client.post(
        f"/api/v1/research-labs/sessions/{session_id}/finding-review/submit",
        headers=headers,
        json={"answers": _correct_finding_review_answers()},
    )
    assert good_finding_response.status_code == 200
    assert good_finding_response.json()["data"]["status"] == "passed"
    assert good_finding_response.json()["data"]["findingReviewPassed"] is True

    bad_report_response = await seeded_client.put(
        f"/api/v1/research-labs/sessions/{session_id}/report",
        headers=headers,
        json={
            "fields": {
                **_accepted_report_fields([]),
                "titleOptionId": "wrong-title",
                "verifiedEvidenceRefs": verified["verifiedEvidenceRefs"],
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
    assert retry["labCompleted"] is False
    assert retry["certificateUnlockable"] is False

    accepted_report_response = await seeded_client.put(
        f"/api/v1/research-labs/sessions/{session_id}/report",
        headers=headers,
        json={"fields": _accepted_report_fields(verified["verifiedEvidenceRefs"])},
    )
    assert accepted_report_response.status_code == 200
    accepted_response = await seeded_client.post(
        f"/api/v1/research-labs/sessions/{session_id}/report/submit", headers=headers
    )
    assert accepted_response.status_code == 200
    accepted = accepted_response.json()["data"]
    assert accepted["status"] == "accepted"
    assert accepted["labCompleted"] is True
    assert accepted["xpAwarded"] == 250
    assert accepted["certificateUnlockable"] is True

    completed_session_response = await seeded_client.get(
        f"/api/v1/research-labs/sessions/{session_id}", headers=headers
    )
    assert completed_session_response.status_code == 200
    completed = completed_session_response.json()["data"]
    assert completed["phase"] == "COMPLETED"
    assert completed["status"] == "completed"
    assert completed["findingReviewPassed"] is True
    assert completed["auditReportBuilderPassed"] is True
    assert completed["certificateUnlockable"] is True

    me_response = await seeded_client.get("/api/v1/auth/me", headers=headers)
    assert me_response.json()["xp"] == 250
    assert me_response.json()["completed_levels"] == 0


async def test_research_lab_session_ownership_is_enforced(seeded_client: AsyncClient) -> None:
    await register_user(seeded_client, email="owner@example.com")
    owner_token = await login_token(seeded_client, email="owner@example.com")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    create_response = await seeded_client.post(
        "/api/v1/research-labs/rl1-account-substitution/sessions", headers=owner_headers
    )
    session_id = create_response.json()["data"]["session_id"]

    await register_user(seeded_client, email="intruder@example.com")
    intruder_token = await login_token(seeded_client, email="intruder@example.com")
    intruder_headers = {"Authorization": f"Bearer {intruder_token}"}

    response = await seeded_client.get(
        f"/api/v1/research-labs/sessions/{session_id}", headers=intruder_headers
    )
    assert response.status_code == 403
