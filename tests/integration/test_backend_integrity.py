import pytest
from httpx import AsyncClient


async def register_user(client: AsyncClient, email: str) -> str:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"username": email.split("@")[0], "email": email, "password": "strong-password"},
    )
    assert resp.status_code == 201
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "strong-password"},
    )
    assert resp.status_code == 200
    return resp.json()["tokens"]["access_token"]


async def create_session(client: AsyncClient, token: str, lab_ref: str = "rl1-account-substitution") -> str:
    resp = await client.post(
        f"/api/v1/research-labs/{lab_ref}/sessions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["data"]["session_id"]


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
        "optionalNotes": None,
    }


EXPLOIT_MAX_BORROW = 400_000
OFFICIAL_MAX_BORROW = 40_000
OFFICIAL_COLLATERAL_START = 50_000


class TestCrossUserAccessDenial:
    async def _assert_forbidden(
        self, client: AsyncClient, token: str, method: str, path: str, **kwargs
    ) -> None:
        resp = await getattr(client, method)(
            path, headers={"Authorization": f"Bearer {token}"}, **kwargs
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_get_session_denied_for_other_user(self, seeded_client: AsyncClient) -> None:
        owner_token = await register_user(seeded_client, "owner@x.com")
        intruder_token = await register_user(seeded_client, "intruder@x.com")
        sid = await create_session(seeded_client, owner_token)
        await self._assert_forbidden(
            seeded_client, intruder_token, "get", f"/api/v1/research-labs/sessions/{sid}"
        )

    @pytest.mark.asyncio
    async def test_verify_objective_denied_for_other_user(self, seeded_client: AsyncClient) -> None:
        owner_token = await register_user(seeded_client, "owner2@x.com")
        intruder_token = await register_user(seeded_client, "intruder2@x.com")
        sid = await create_session(seeded_client, owner_token)
        await self._assert_forbidden(
            seeded_client,
            intruder_token,
            "post",
            f"/api/v1/research-labs/sessions/{sid}/verify-objective",
        )


class TestExploitProvenance:
    @pytest.mark.asyncio
    async def test_verify_fails_before_any_action(self, seeded_client: AsyncClient) -> None:
        token = await register_user(seeded_client, "probe0@x.com")
        sid = await create_session(seeded_client, token)
        headers = {"Authorization": f"Bearer {token}"}
        resp = await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/verify-objective", headers=headers
        )
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["passed"] is False
        assert body["impactVerified"] is False

    @pytest.mark.asyncio
    async def test_verify_fails_after_counterfeit_deposit_only(
        self, seeded_client: AsyncClient
    ) -> None:
        token = await register_user(seeded_client, "probe1@x.com")
        sid = await create_session(seeded_client, token)
        headers = {"Authorization": f"Bearer {token}"}
        await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
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
        resp = await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/verify-objective", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["passed"] is False

    @pytest.mark.asyncio
    async def test_withdrawal_without_invalid_credit_is_not_verified(
        self, seeded_client: AsyncClient
    ) -> None:
        token = await register_user(seeded_client, "probe2@x.com")
        sid = await create_session(seeded_client, token)
        headers = {"Authorization": f"Bearer {token}"}
        tx_resp = await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
            headers=headers,
            json={"action_type": "WITHDRAW_AGAINST_CREDIT", "parameters": {"amount": 50000}},
        )
        assert tx_resp.status_code == 200
        assert tx_resp.json()["data"]["execution_status"] == "failure"
        verify_resp = await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/verify-objective", headers=headers
        )
        assert verify_resp.json()["data"]["passed"] is False

    @pytest.mark.asyncio
    async def test_full_exploit_marks_impact_verified(self, seeded_client: AsyncClient) -> None:
        token = await register_user(seeded_client, "probe3@x.com")
        sid = await create_session(seeded_client, token)
        headers = {"Authorization": f"Bearer {token}"}
        await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
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
        await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
            headers=headers,
            json={"action_type": "WITHDRAW_AGAINST_CREDIT", "parameters": {"amount": EXPLOIT_MAX_BORROW}},
        )
        resp = await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/verify-objective", headers=headers
        )
        body = resp.json()["data"]
        assert body["passed"] is True
        assert body["impactVerified"] is True
        assert body["reportUnlocked"] is True
        assert body["certificateUnlockable"] is False
        assert body["evidence"]["impactChecklist"]["maxDrainSatisfied"] is True

    @pytest.mark.asyncio
    async def test_exploit_partial_borrow_does_not_verify(self, seeded_client: AsyncClient) -> None:
        token = await register_user(seeded_client, "probe4@x.com")
        sid = await create_session(seeded_client, token)
        headers = {"Authorization": f"Bearer {token}"}
        await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
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
        await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
            headers=headers,
            json={"action_type": "WITHDRAW_AGAINST_CREDIT", "parameters": {"amount": 50_000}},
        )
        resp = await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/verify-objective", headers=headers
        )
        body = resp.json()["data"]
        assert body["passed"] is False
        assert "max borrow amount" in body["failureReason"]


class TestCollateralVaultMatrix:
    @pytest.mark.asyncio
    async def test_official_collateral_and_official_vault_succeeds_but_not_verified(
        self, seeded_client: AsyncClient
    ) -> None:
        token = await register_user(seeded_client, "matrix1@x.com")
        sid = await create_session(seeded_client, token)
        headers = {"Authorization": f"Bearer {token}"}
        resp = await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
            headers=headers,
            json={
                "action_type": "DEPOSIT_COLLATERAL",
                "parameters": {
                    "amount": 50000,
                    "collateral_account_ref": "official_collateral_account",
                    "vault_account_ref": "official_vault_account",
                },
            },
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["execution_status"] == "success"
        assert resp.json()["data"]["protocolState"]["depositPathType"] == "official"
        assert resp.json()["data"]["protocolState"]["maxBorrow"] == OFFICIAL_MAX_BORROW
        position_resp = await seeded_client.get(
            f"/api/v1/research-labs/sessions/{sid}/accounts/position",
            headers=headers,
        )
        assert position_resp.status_code == 200
        position_data = position_resp.json()["data"]["account"]["data"]
        assert position_data["creditedCollateral"] == OFFICIAL_COLLATERAL_START
        assert position_data["availableBorrow"] == OFFICIAL_MAX_BORROW
        assert position_data["depositPathType"] == "official"
        borrow_resp = await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
            headers=headers,
            json={"action_type": "WITHDRAW_AGAINST_CREDIT", "parameters": {"amount": OFFICIAL_MAX_BORROW}},
        )
        assert borrow_resp.status_code == 200
        assert borrow_resp.json()["data"]["execution_status"] == "success"
        assert borrow_resp.json()["data"]["protocolState"]["availableBorrow"] == 0
        resp_v = await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/verify-objective", headers=headers
        )
        assert resp_v.json()["data"]["passed"] is False

    @pytest.mark.asyncio
    async def test_candidate_collateral_and_official_vault_fails(
        self, seeded_client: AsyncClient
    ) -> None:
        token = await register_user(seeded_client, "matrix2@x.com")
        sid = await create_session(seeded_client, token)
        headers = {"Authorization": f"Bearer {token}"}
        resp = await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
            headers=headers,
            json={
                "action_type": "DEPOSIT_COLLATERAL",
                "parameters": {
                    "amount": 50000,
                    "collateral_account_ref": "attacker_collateral_account",
                    "vault_account_ref": "official_vault_account",
                },
            },
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["execution_status"] == "failure"

    @pytest.mark.asyncio
    async def test_official_collateral_and_external_vault_fails(
        self, seeded_client: AsyncClient
    ) -> None:
        token = await register_user(seeded_client, "matrix3@x.com")
        sid = await create_session(seeded_client, token)
        headers = {"Authorization": f"Bearer {token}"}
        resp = await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
            headers=headers,
            json={
                "action_type": "DEPOSIT_COLLATERAL",
                "parameters": {
                    "amount": 50000,
                    "collateral_account_ref": "official_collateral_account",
                    "vault_account_ref": "counterfeit_vault_account",
                },
            },
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["execution_status"] == "failure"


class TestCompletionGates:
    @pytest.mark.asyncio
    async def test_report_with_wrong_option_ids_is_rejected(self, seeded_client: AsyncClient) -> None:
        token = await register_user(seeded_client, "report0@x.com")
        sid = await create_session(seeded_client, token)
        headers = {"Authorization": f"Bearer {token}"}
        await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
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
        await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
            headers=headers,
            json={"action_type": "WITHDRAW_AGAINST_CREDIT", "parameters": {"amount": EXPLOIT_MAX_BORROW}},
        )
        verify = await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/verify-objective", headers=headers
        )
        evidence_refs = verify.json()["data"]["verifiedEvidenceRefs"]
        await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/finding-review/submit",
            headers=headers,
            json={"answers": _correct_finding_review_answers()},
        )
        await seeded_client.put(
            f"/api/v1/research-labs/sessions/{sid}/report",
            headers=headers,
            json={
                "fields": {
                    **_accepted_report_fields(evidence_refs),
                    "titleOptionId": "wrong_title",
                }
            },
        )
        resp = await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/report/submit", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "retry"

    @pytest.mark.asyncio
    async def test_report_without_verified_evidence_refs_is_rejected(
        self, seeded_client: AsyncClient
    ) -> None:
        token = await register_user(seeded_client, "report1@x.com")
        sid = await create_session(seeded_client, token)
        headers = {"Authorization": f"Bearer {token}"}
        await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
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
        await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
            headers=headers,
            json={"action_type": "WITHDRAW_AGAINST_CREDIT", "parameters": {"amount": EXPLOIT_MAX_BORROW}},
        )
        await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/verify-objective", headers=headers
        )
        await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/finding-review/submit",
            headers=headers,
            json={"answers": _correct_finding_review_answers()},
        )
        await seeded_client.put(
            f"/api/v1/research-labs/sessions/{sid}/report",
            headers=headers,
            json={"fields": _accepted_report_fields([])},
        )
        resp = await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/report/submit", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "retry"

    @pytest.mark.asyncio
    async def test_certificate_unlockable_only_after_full_backend_completion(
        self, seeded_client: AsyncClient
    ) -> None:
        token = await register_user(seeded_client, "report2@x.com")
        sid = await create_session(seeded_client, token)
        headers = {"Authorization": f"Bearer {token}"}
        await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
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
        await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
            headers=headers,
            json={"action_type": "WITHDRAW_AGAINST_CREDIT", "parameters": {"amount": EXPLOIT_MAX_BORROW}},
        )
        verify = await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/verify-objective", headers=headers
        )
        assert verify.json()["data"]["certificateUnlockable"] is False
        evidence_refs = verify.json()["data"]["verifiedEvidenceRefs"]
        review = await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/finding-review/submit",
            headers=headers,
            json={"answers": _correct_finding_review_answers()},
        )
        assert review.json()["data"]["certificateUnlockable"] is False
        await seeded_client.put(
            f"/api/v1/research-labs/sessions/{sid}/report",
            headers=headers,
            json={"fields": _accepted_report_fields(evidence_refs)},
        )
        report = await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/report/submit", headers=headers
        )
        assert report.json()["data"]["certificateUnlockable"] is True

    @pytest.mark.asyncio
    async def test_reset_relocks_report_and_clears_impact(self, seeded_client: AsyncClient) -> None:
        token = await register_user(seeded_client, "reset0@x.com")
        sid = await create_session(seeded_client, token)
        headers = {"Authorization": f"Bearer {token}"}
        await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
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
        await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
            headers=headers,
            json={"action_type": "WITHDRAW_AGAINST_CREDIT", "parameters": {"amount": EXPLOIT_MAX_BORROW}},
        )
        await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/verify-objective", headers=headers
        )
        reset_resp = await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/reset", headers=headers
        )
        assert reset_resp.status_code == 200
        verify_resp = await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/verify-objective", headers=headers
        )
        report_resp = await seeded_client.get(
            f"/api/v1/research-labs/sessions/{sid}/report", headers=headers
        )
        assert verify_resp.json()["data"]["passed"] is False
        assert verify_resp.json()["data"]["impactVerified"] is False
        assert report_resp.json()["data"]["status"] == "locked"
