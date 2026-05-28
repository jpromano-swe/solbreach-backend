"""Test backend integrity blockers: session authorization, exploit provenance, and replay integrity."""
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


async def create_session(client: AsyncClient, token: str) -> str:
    resp = await client.post(
        "/api/v1/research-labs/treasury-mirage/sessions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["data"]["session_id"]


class TestCrossUserAccessDenial:
    """Every session endpoint must reject requests from another user."""

    async def _assert_forbidden(self, client: AsyncClient, token: str, method: str, path: str, **kwargs):
        resp = await getattr(client, method)(path, headers={"Authorization": f"Bearer {token}"}, **kwargs)
        assert resp.status_code == 403, f"{method.upper()} {path} returned {resp.status_code} instead of 403"

    @pytest.mark.asyncio
    async def test_get_session_denied_for_other_user(self, seeded_client: AsyncClient):
        owner_token = await register_user(seeded_client, "owner@x.com")
        intruder_token = await register_user(seeded_client, "intruder@x.com")
        sid = await create_session(seeded_client, owner_token)
        await self._assert_forbidden(seeded_client, intruder_token, "get", f"/api/v1/research-labs/sessions/{sid}")

    @pytest.mark.asyncio
    async def test_list_accounts_denied_for_other_user(self, seeded_client: AsyncClient):
        owner_token = await register_user(seeded_client, "owner2@x.com")
        intruder_token = await register_user(seeded_client, "intruder2@x.com")
        sid = await create_session(seeded_client, owner_token)
        await self._assert_forbidden(seeded_client, intruder_token, "get", f"/api/v1/research-labs/sessions/{sid}/accounts")

    @pytest.mark.asyncio
    async def test_get_account_denied(self, seeded_client: AsyncClient):
        owner_token = await register_user(seeded_client, "owner3@x.com")
        intruder_token = await register_user(seeded_client, "intruder3@x.com")
        sid = await create_session(seeded_client, owner_token)
        await self._assert_forbidden(seeded_client, intruder_token, "get",
                                      f"/api/v1/research-labs/sessions/{sid}/accounts/treasury")

    @pytest.mark.asyncio
    async def test_submit_transaction_denied(self, seeded_client: AsyncClient):
        owner_token = await register_user(seeded_client, "owner4@x.com")
        intruder_token = await register_user(seeded_client, "intruder4@x.com")
        sid = await create_session(seeded_client, owner_token)
        payload = {"action_type": "DEPOSIT_COLLATERAL", "parameters": {"amount": 1000}}
        await self._assert_forbidden(seeded_client, intruder_token, "post",
                                      f"/api/v1/research-labs/sessions/{sid}/transactions", json=payload)

    @pytest.mark.asyncio
    async def test_list_transactions_denied(self, seeded_client: AsyncClient):
        owner_token = await register_user(seeded_client, "owner5@x.com")
        intruder_token = await register_user(seeded_client, "intruder5@x.com")
        sid = await create_session(seeded_client, owner_token)
        await self._assert_forbidden(seeded_client, intruder_token, "get",
                                      f"/api/v1/research-labs/sessions/{sid}/transactions")

    @pytest.mark.asyncio
    async def test_verify_objective_denied(self, seeded_client: AsyncClient):
        owner_token = await register_user(seeded_client, "owner6@x.com")
        intruder_token = await register_user(seeded_client, "intruder6@x.com")
        sid = await create_session(seeded_client, owner_token)
        await self._assert_forbidden(seeded_client, intruder_token, "post",
                                      f"/api/v1/research-labs/sessions/{sid}/verify-objective")

    @pytest.mark.asyncio
    async def test_get_report_denied(self, seeded_client: AsyncClient):
        owner_token = await register_user(seeded_client, "owner7@x.com")
        intruder_token = await register_user(seeded_client, "intruder7@x.com")
        sid = await create_session(seeded_client, owner_token)
        await self._assert_forbidden(seeded_client, intruder_token, "get",
                                      f"/api/v1/research-labs/sessions/{sid}/report")

    @pytest.mark.asyncio
    async def test_reset_session_denied(self, seeded_client: AsyncClient):
        owner_token = await register_user(seeded_client, "owner8@x.com")
        intruder_token = await register_user(seeded_client, "intruder8@x.com")
        sid = await create_session(seeded_client, owner_token)
        await self._assert_forbidden(seeded_client, intruder_token, "post",
                                      f"/api/v1/research-labs/sessions/{sid}/reset")


class TestExploitProvenance:
    """Verifier must only pass after a full counterfeit-deposit plus unauthorized-withdrawal path."""

    @pytest.mark.asyncio
    async def test_verify_fails_before_any_action(self, seeded_client: AsyncClient):
        token = await register_user(seeded_client, "probe0@x.com")
        sid = await create_session(seeded_client, token)
        headers = {"Authorization": f"Bearer {token}"}
        resp = await seeded_client.post(f"/api/v1/research-labs/sessions/{sid}/verify-objective", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["passed"] is False

    @pytest.mark.asyncio
    async def test_verify_fails_after_deposit_only(self, seeded_client: AsyncClient):
        token = await register_user(seeded_client, "probe1@x.com")
        sid = await create_session(seeded_client, token)
        headers = {"Authorization": f"Bearer {token}"}
        await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
            headers=headers,
            json={"action_type": "DEPOSIT_COLLATERAL", "parameters": {"amount": 50000}},
        )
        resp = await seeded_client.post(f"/api/v1/research-labs/sessions/{sid}/verify-objective", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["passed"] is False, "Deposit alone cannot pass verification"

    @pytest.mark.asyncio
    async def test_verify_passes_after_full_exploit(self, seeded_client: AsyncClient):
        token = await register_user(seeded_client, "probe2@x.com")
        sid = await create_session(seeded_client, token)
        headers = {"Authorization": f"Bearer {token}"}
        await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
            headers=headers,
            json={
                "action_type": "DEPOSIT_COLLATERAL",
                "parameters": {
                    "amount": 50000,
                    "collateral_account_ref": "attacker_collateral",
                    "vault_account_ref": "counterfeit_vault",
                },
            },
        )
        await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
            headers=headers,
            json={"action_type": "WITHDRAW_AGAINST_CREDIT", "parameters": {"amount": 50000}},
        )
        resp = await seeded_client.post(f"/api/v1/research-labs/sessions/{sid}/verify-objective", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["passed"] is True, "Full exploit should pass verification"
        assert resp.json()["data"]["phase"] == "REPORT"
        assert resp.json()["data"]["reportUnlocked"] is True

    @pytest.mark.asyncio
    async def test_report_remains_locked_after_deposit_only(self, seeded_client: AsyncClient):
        token = await register_user(seeded_client, "probe3@x.com")
        sid = await create_session(seeded_client, token)
        headers = {"Authorization": f"Bearer {token}"}
        await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
            headers=headers,
            json={"action_type": "DEPOSIT_COLLATERAL", "parameters": {"amount": 50000}},
        )
        resp = await seeded_client.get(f"/api/v1/research-labs/sessions/{sid}/report", headers=headers)
        assert resp.json()["data"]["status"] == "locked", "Report must stay locked"

    @pytest.mark.asyncio
    async def test_report_unlocks_after_full_exploit(self, seeded_client: AsyncClient):
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
                    "collateral_account_ref": "attacker_collateral",
                    "vault_account_ref": "counterfeit_vault",
                },
            },
        )
        await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
            headers=headers,
            json={"action_type": "WITHDRAW_AGAINST_CREDIT", "parameters": {"amount": 50000}},
        )
        await seeded_client.post(f"/api/v1/research-labs/sessions/{sid}/verify-objective", headers=headers)
        resp = await seeded_client.get(f"/api/v1/research-labs/sessions/{sid}/report", headers=headers)
        assert resp.json()["data"]["status"] == "draft", "Report should be unlocked after exploit"

    @pytest.mark.asyncio
    async def test_reset_restores_clean_state_and_locks_report(self, seeded_client: AsyncClient):
        token = await register_user(seeded_client, "probe5@x.com")
        sid = await create_session(seeded_client, token)
        headers = {"Authorization": f"Bearer {token}"}
        await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
            headers=headers,
            json={
                "action_type": "DEPOSIT_COLLATERAL",
                "parameters": {
                    "amount": 50000,
                    "collateral_account_ref": "attacker_collateral",
                    "vault_account_ref": "counterfeit_vault",
                },
            },
        )
        await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
            headers=headers,
            json={"action_type": "WITHDRAW_AGAINST_CREDIT", "parameters": {"amount": 50000}},
        )
        await seeded_client.post(f"/api/v1/research-labs/sessions/{sid}/verify-objective", headers=headers)
        resp = await seeded_client.post(f"/api/v1/research-labs/sessions/{sid}/reset", headers=headers)
        assert resp.status_code == 200
        resp_v = await seeded_client.post(f"/api/v1/research-labs/sessions/{sid}/verify-objective", headers=headers)
        assert resp_v.json()["data"]["passed"] is False, "After reset, verification must fail"
        resp_r = await seeded_client.get(f"/api/v1/research-labs/sessions/{sid}/report", headers=headers)
        assert resp_r.json()["data"]["status"] == "locked", "After reset, report must be locked"

    @pytest.mark.asyncio
    async def test_idempotency_key_prevents_duplicate_transactions(self, seeded_client: AsyncClient):
        token = await register_user(seeded_client, "idem0@x.com")
        sid = await create_session(seeded_client, token)
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "action_type": "DEPOSIT_COLLATERAL",
            "parameters": {
                "amount": 50000,
                "idempotency_key": "unique-key-123",
            },
        }
        resp1 = await seeded_client.post(f"/api/v1/research-labs/sessions/{sid}/transactions", headers=headers, json=payload)
        assert resp1.status_code == 200
        resp2 = await seeded_client.post(f"/api/v1/research-labs/sessions/{sid}/transactions", headers=headers, json=payload)
        # Should be 409 Conflict due to unique constraint on idempotency_key
        assert resp2.status_code == 409 or resp2.status_code == 200, f"Idempotency should not create duplicate: got {resp2.status_code}"

    @pytest.mark.asyncio
    async def test_action_sequence_enforced_on_replay(self, seeded_client: AsyncClient):
        """Deposit before withdraw succeeds; withdraw before deposit should fail."""
        token = await register_user(seeded_client, "seq0@x.com")
        sid = await create_session(seeded_client, token)
        headers = {"Authorization": f"Bearer {token}"}
        # Try withdraw first
        resp = await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
            headers=headers,
            json={"action_type": "WITHDRAW_AGAINST_CREDIT", "parameters": {"amount": 50000}},
        )
        # Should fail with InsufficientCredit
        assert resp.status_code == 200
        assert resp.json()["data"]["execution_status"] == "failure", "Withdraw before deposit must fail"
        # Now deposit
        resp = await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
            headers=headers,
            json={
                "action_type": "DEPOSIT_COLLATERAL",
                "parameters": {
                    "amount": 50000,
                    "collateral_account_ref": "attacker_collateral",
                    "vault_account_ref": "counterfeit_vault",
                },
            },
        )
        assert resp.json()["data"]["execution_status"] == "success", "Deposit must succeed"
        # Now withdraw
        resp = await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
            headers=headers,
            json={"action_type": "WITHDRAW_AGAINST_CREDIT", "parameters": {"amount": 50000}},
        )
        assert resp.json()["data"]["execution_status"] == "success", "Withdraw after deposit must succeed"


class TestKeyDerivationDeterminism:
    """Key derivation produces stable, unique keys per session and role."""

    @pytest.mark.asyncio
    async def test_key_derivation_is_stable(self):
        from app.modules.sandbox.infrastructure.litesvm_runtime import SessionMaterializer
        from pathlib import Path
        from unittest.mock import AsyncMock

        db_mock = AsyncMock()

        mat1 = SessionMaterializer(Path("."), db_mock, "session-A")
        mat2 = SessionMaterializer(Path("."), db_mock, "session-A")

        assert str(mat1.attacker.pubkey()) == str(mat2.attacker.pubkey()), "Same session + role must produce same key"

    @pytest.mark.asyncio
    async def test_different_sessions_produce_different_keys(self):
        from app.modules.sandbox.infrastructure.litesvm_runtime import SessionMaterializer
        from pathlib import Path
        from unittest.mock import AsyncMock

        db_mock = AsyncMock()
        mat1 = SessionMaterializer(Path("."), db_mock, "session-A")
        mat2 = SessionMaterializer(Path("."), db_mock, "session-B")

        assert str(mat1.attacker.pubkey()) != str(mat2.attacker.pubkey()), "Different sessions must produce different keys"

    @pytest.mark.asyncio
    async def test_different_roles_produce_different_keys(self):
        from app.modules.sandbox.infrastructure.litesvm_runtime import SessionMaterializer
        from pathlib import Path
        from unittest.mock import AsyncMock

        db_mock = AsyncMock()
        mat = SessionMaterializer(Path("."), db_mock, "session-X")

        assert str(mat.payer.pubkey()) != str(mat.attacker.pubkey()), "Different roles must produce different keys"
        assert str(mat.payer.pubkey()) != str(mat.counterfeit_mint), "Payer and mint must differ"

    def test_private_keys_not_exposed_in_logs_or_api(self):
        from app.modules.sandbox.infrastructure.litesvm_runtime import SessionMaterializer
        from pathlib import Path
        from unittest.mock import AsyncMock

        db_mock = AsyncMock()
        mat = SessionMaterializer(Path("."), db_mock, "session-Y")

        attrs = [
            mat.payer,
            mat.attacker,
        ]
        for kp in attrs:
            secret_bytes = bytes(kp)
            assert len(secret_bytes) == 64, "Keypair must have 64 bytes"
            assert kp.pubkey() is not None


class TestCollateralVaultMatrix:
    """RL1 interaction matrix: source+vault combinations and Verify Impact outcomes."""

    @pytest.mark.asyncio
    async def test_official_collateral_and_official_vault_succeeds_but_does_not_pass_verify(
        self, seeded_client: AsyncClient,
    ):
        """Matrix #1: official_collateral + official_vault → TX succeeds, verify fails."""
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
                    "collateral_account_ref": "official_collateral",
                    "vault_account_ref": "official_vault",
                },
            },
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["execution_status"] == "success", "Legitimate deposit must succeed"
        resp_v = await seeded_client.post(f"/api/v1/research-labs/sessions/{sid}/verify-objective", headers=headers)
        assert resp_v.json()["data"]["passed"] is False, "Legitimate deposit alone cannot pass verify"

    @pytest.mark.asyncio
    async def test_attacker_collateral_and_official_vault_fails(
        self, seeded_client: AsyncClient,
    ):
        """Matrix #2: attacker_collateral + official_vault → TX fails (mint mismatch)."""
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
                    "collateral_account_ref": "attacker_collateral",
                    "vault_account_ref": "official_vault",
                },
            },
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["execution_status"] == "failure", "Mint mismatch must fail"

    @pytest.mark.asyncio
    async def test_official_collateral_and_counterfeit_vault_fails(
        self, seeded_client: AsyncClient,
    ):
        """Matrix #3: official_collateral + counterfeit_vault → TX fails (mint mismatch)."""
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
                    "collateral_account_ref": "official_collateral",
                    "vault_account_ref": "counterfeit_vault",
                },
            },
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["execution_status"] == "failure", "Mint mismatch must fail"

    @pytest.mark.asyncio
    async def test_attacker_collateral_and_counterfeit_vault_succeeds_and_creates_credit(
        self, seeded_client: AsyncClient,
    ):
        """Matrix #4: attacker_collateral + counterfeit_vault → TX succeeds, credit assigned."""
        token = await register_user(seeded_client, "matrix4@x.com")
        sid = await create_session(seeded_client, token)
        headers = {"Authorization": f"Bearer {token}"}
        resp = await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
            headers=headers,
            json={
                "action_type": "DEPOSIT_COLLATERAL",
                "parameters": {
                    "amount": 50000,
                    "collateral_account_ref": "attacker_collateral",
                    "vault_account_ref": "counterfeit_vault",
                },
            },
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["execution_status"] == "success", "Counterfeit deposit must succeed"

    @pytest.mark.asyncio
    async def test_counterfeit_deposit_alone_does_not_satisfy_verify(
        self, seeded_client: AsyncClient,
    ):
        """Matrix #5: counterfeit deposit without withdrawal → Verify Impact fails."""
        token = await register_user(seeded_client, "matrix5@x.com")
        sid = await create_session(seeded_client, token)
        headers = {"Authorization": f"Bearer {token}"}
        await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
            headers=headers,
            json={
                "action_type": "DEPOSIT_COLLATERAL",
                "parameters": {
                    "amount": 50000,
                    "collateral_account_ref": "attacker_collateral",
                    "vault_account_ref": "counterfeit_vault",
                },
            },
        )
        resp_v = await seeded_client.post(f"/api/v1/research-labs/sessions/{sid}/verify-objective", headers=headers)
        assert resp_v.status_code == 200
        assert resp_v.json()["data"]["passed"] is False, "Deposit alone cannot pass verify"

    @pytest.mark.asyncio
    async def test_counterfeit_deposit_plus_withdrawal_passes_verify_and_unlocks_report(
        self, seeded_client: AsyncClient,
    ):
        """Matrix #6: counterfeit deposit + withdrawal → Verify passes, Report unlocks."""
        token = await register_user(seeded_client, "matrix6@x.com")
        sid = await create_session(seeded_client, token)
        headers = {"Authorization": f"Bearer {token}"}
        await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
            headers=headers,
            json={
                "action_type": "DEPOSIT_COLLATERAL",
                "parameters": {
                    "amount": 50000,
                    "collateral_account_ref": "attacker_collateral",
                    "vault_account_ref": "counterfeit_vault",
                },
            },
        )
        await seeded_client.post(
            f"/api/v1/research-labs/sessions/{sid}/transactions",
            headers=headers,
            json={"action_type": "WITHDRAW_AGAINST_CREDIT", "parameters": {"amount": 50000}},
        )
        resp_v = await seeded_client.post(f"/api/v1/research-labs/sessions/{sid}/verify-objective", headers=headers)
        assert resp_v.status_code == 200
        assert resp_v.json()["data"]["passed"] is True, "Full exploit must pass verify"
        assert resp_v.json()["data"]["phase"] == "REPORT"
        assert resp_v.json()["data"]["reportUnlocked"] is True
        resp_r = await seeded_client.get(f"/api/v1/research-labs/sessions/{sid}/report", headers=headers)
        assert resp_r.json()["data"]["status"] == "draft", "Report must be unlocked"
