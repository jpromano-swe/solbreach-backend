from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class VerificationCheckResult:
    name: str
    passed: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class VerificationResult:
    verified: bool
    message: str
    checks: list[VerificationCheckResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "verified": self.verified,
            "message": self.message,
            "checks": [
                {
                    "name": check.name,
                    "passed": check.passed,
                    "message": check.message,
                    "details": check.details,
                }
                for check in self.checks
            ],
        }


class VerificationStrategy(Protocol):
    name: str

    def verify(
        self, config: dict[str, Any], payload: dict[str, Any]
    ) -> VerificationCheckResult: ...


class SessionBindingStrategy:
    name = "session_binding"

    def verify(self, config: dict[str, Any], payload: dict[str, Any]) -> VerificationCheckResult:
        expected_session_id = config.get("expected_session_id")
        expected_wallet_address = config.get("expected_wallet_address")
        session_id = payload.get("level_session_id")
        wallet_address = payload.get("wallet_address")
        if expected_session_id and session_id != expected_session_id:
            return VerificationCheckResult(
                self.name,
                False,
                "Submission is not tied to the active level session",
                {"expected_session_id": expected_session_id, "actual_session_id": session_id},
            )
        if expected_wallet_address and wallet_address != expected_wallet_address:
            return VerificationCheckResult(
                self.name,
                False,
                "Submission wallet does not match setup wallet",
                {
                    "expected_wallet_address": expected_wallet_address,
                    "actual_wallet_address": wallet_address,
                },
            )
        return VerificationCheckResult(self.name, True, "Session binding accepted")


class ReplayProtectionStrategy:
    name = "replay_protection"

    def verify(self, config: dict[str, Any], payload: dict[str, Any]) -> VerificationCheckResult:
        if payload.get("tx_signature_reused") is True:
            return VerificationCheckResult(
                self.name,
                False,
                "Transaction signature was already submitted",
                {"transaction_signature": payload.get("transaction_signature")},
            )
        return VerificationCheckResult(self.name, True, "Transaction signature is unique")


class TransactionSignatureStrategy:
    name = "transaction_signature"

    def verify(self, config: dict[str, Any], payload: dict[str, Any]) -> VerificationCheckResult:
        signature = payload.get("transaction_signature")
        expected_signature = config.get("expected_signature")
        if not isinstance(signature, str) or len(signature) < 16:
            return VerificationCheckResult(
                self.name, False, "Missing or invalid transaction signature"
            )
        if expected_signature and signature != expected_signature:
            return VerificationCheckResult(self.name, False, "Transaction signature does not match")
        if config.get("require_success", True) and payload.get("transaction_succeeded") is not True:
            return VerificationCheckResult(
                self.name, False, "Transaction was not marked successful"
            )
        return VerificationCheckResult(self.name, True, "Transaction proof accepted")


class SolanaTransactionStrategy:
    name = "solana_transaction"

    def verify(self, config: dict[str, Any], payload: dict[str, Any]) -> VerificationCheckResult:
        transaction = payload.get("onchain_transaction")
        if not isinstance(transaction, dict) or transaction.get("exists") is not True:
            return VerificationCheckResult(self.name, False, "Transaction was not found on devnet")
        if config.get("require_success", True) and transaction.get("succeeded") is not True:
            return VerificationCheckResult(self.name, False, "Transaction failed on devnet")

        wallet_address = payload.get("wallet_address")
        signers = transaction.get("signers") or []
        if config.get("require_wallet_signer", True) and wallet_address not in signers:
            return VerificationCheckResult(
                self.name,
                False,
                "Connected wallet did not sign the transaction",
                {"wallet_address": wallet_address, "signers": signers},
            )

        challenge_context = payload.get("challenge_context") or {}
        required_accounts = []
        if config.get("require_challenge_accounts", True):
            required_accounts = list(challenge_context.get("required_accounts") or [])
        required_accounts.extend(config.get("required_accounts", []))
        account_keys = set(transaction.get("account_keys") or [])
        missing_accounts = [account for account in required_accounts if account not in account_keys]
        if missing_accounts:
            return VerificationCheckResult(
                self.name,
                False,
                "Transaction did not include required challenge accounts",
                {"missing_accounts": missing_accounts},
            )

        modified_account_labels = config.get("required_modified_account_labels", [])
        deltas = transaction.get("token_balance_deltas") or {}
        missing_modifications = [
            label
            for label in modified_account_labels
            if challenge_context.get(label) not in deltas
        ]
        if missing_modifications:
            return VerificationCheckResult(
                self.name,
                False,
                "Transaction did not modify expected token accounts",
                {"missing_modified_account_labels": missing_modifications},
            )
        return VerificationCheckResult(self.name, True, "Solana transaction proof accepted")


class PDAStateStrategy:
    name = "pda_state"

    def verify(self, config: dict[str, Any], payload: dict[str, Any]) -> VerificationCheckResult:
        actual = payload.get("pda_state")
        expected = config.get("expected", {})
        if not isinstance(actual, dict):
            return VerificationCheckResult(self.name, False, "Missing PDA state proof")
        mismatches = _collect_mismatches(expected, actual)
        if mismatches:
            return VerificationCheckResult(
                self.name,
                False,
                "PDA state did not match expected outcome",
                {"mismatches": mismatches},
            )
        return VerificationCheckResult(self.name, True, "PDA state proof accepted")


class TokenBalanceStrategy:
    name = "token_balance"

    def verify(self, config: dict[str, Any], payload: dict[str, Any]) -> VerificationCheckResult:
        actual = payload.get("token_balances")
        expected = config.get("expected", {})
        if not isinstance(actual, dict):
            return VerificationCheckResult(self.name, False, "Missing token balance proof")
        mismatches = _collect_mismatches(expected, actual)
        if mismatches:
            return VerificationCheckResult(
                self.name,
                False,
                "Token balances did not match expected outcome",
                {"mismatches": mismatches},
            )
        return VerificationCheckResult(self.name, True, "Token balance proof accepted")


class PDACommanderHijackStrategy:
    name = "pda_commander_hijack"

    def verify(self, config: dict[str, Any], payload: dict[str, Any]) -> VerificationCheckResult:
        transaction = payload.get("onchain_transaction")
        if not isinstance(transaction, dict) or transaction.get("exists") is not True:
            return VerificationCheckResult(self.name, False, "Transaction was not found on devnet")

        challenge_context = payload.get("challenge_context") or {}
        exploit_parameters = challenge_context.get("exploit_parameters") or {}
        if exploit_parameters.get("vulnerability") != "static_pda_commander_hijack":
            return VerificationCheckResult(
                self.name,
                False,
                "Challenge context is not a static PDA commander hijack",
                {"vulnerability": exploit_parameters.get("vulnerability")},
            )

        account_keys = set(transaction.get("account_keys") or [])
        required_labels = config.get(
            "required_account_labels",
            [
                "commander_registry_pda",
                "trusted_commander_pda",
                "hijacked_commander_pda",
                "authority_record_pda",
                "wallet_address",
            ],
        )
        missing_labels = [
            label
            for label in required_labels
            if not challenge_context.get(label) or challenge_context.get(label) not in account_keys
        ]
        if missing_labels:
            return VerificationCheckResult(
                self.name,
                False,
                "Transaction did not include the static PDA commander hijack accounts",
                {"missing_account_labels": missing_labels},
            )

        expected_commander = challenge_context.get("expected_commander_after_hijack")
        wallet_address = payload.get("wallet_address")
        if expected_commander and expected_commander != wallet_address:
            return VerificationCheckResult(
                self.name,
                False,
                "Expected hijacked commander does not match submitting wallet",
                {"expected_commander": expected_commander, "wallet_address": wallet_address},
            )

        return VerificationCheckResult(
            self.name,
            True,
            "Static PDA commander hijack proof accepted",
            {"checked_account_labels": required_labels},
        )


class DelegatedCPIExploitStrategy:
    name = "delegated_cpi_exploit"

    def verify(self, config: dict[str, Any], payload: dict[str, Any]) -> VerificationCheckResult:
        transaction = payload.get("onchain_transaction")
        if not isinstance(transaction, dict) or transaction.get("exists") is not True:
            return VerificationCheckResult(self.name, False, "Transaction was not found on devnet")

        challenge_context = payload.get("challenge_context") or {}
        exploit_parameters = challenge_context.get("exploit_parameters") or {}
        if exploit_parameters.get("vulnerability") != "arbitrary_cpi_delegated_signer_abuse":
            return VerificationCheckResult(
                self.name,
                False,
                "Challenge context is not an arbitrary CPI delegated signer exploit",
                {"vulnerability": exploit_parameters.get("vulnerability")},
            )

        account_keys = set(transaction.get("account_keys") or [])
        required_labels = config.get(
            "required_account_labels",
            [
                "wallet_address",
                "guild_authority_pda",
                "level3_state_pda",
                "bounty_vault_pda",
                "trusted_cpi_program",
                "attacker_cpi_program",
                "player_reward_account",
                "authority_record_pda",
            ],
        )
        missing_labels = [
            label
            for label in required_labels
            if not challenge_context.get(label) or challenge_context.get(label) not in account_keys
        ]
        if missing_labels:
            return VerificationCheckResult(
                self.name,
                False,
                "Transaction did not include the delegated-CPI exploit account set",
                {"missing_account_labels": missing_labels},
            )

        expected_sequence = exploit_parameters.get("expected_sequence")
        required_sequence = config.get("expected_sequence", ["target", "signer", "vault", "reward"])
        if expected_sequence != required_sequence:
            return VerificationCheckResult(
                self.name,
                False,
                "Delegated-CPI exploit sequence does not match the expected path",
                {"expected_sequence": required_sequence, "actual_sequence": expected_sequence},
            )

        return VerificationCheckResult(
            self.name,
            True,
            "Arbitrary CPI delegated signer proof accepted",
            {"checked_account_labels": required_labels, "expected_sequence": required_sequence},
        )


class DataMatchingExploitStrategy:
    name = "data_matching_exploit"

    def verify(self, config: dict[str, Any], payload: dict[str, Any]) -> VerificationCheckResult:
        transaction = payload.get("onchain_transaction")
        if not isinstance(transaction, dict) or transaction.get("exists") is not True:
            return VerificationCheckResult(self.name, False, "Transaction was not found on devnet")

        challenge_context = payload.get("challenge_context") or {}
        exploit_parameters = challenge_context.get("exploit_parameters") or {}
        if exploit_parameters.get("vulnerability") != "data_matching":
            return VerificationCheckResult(
                self.name,
                False,
                "Challenge context is not a data matching exploit",
                {"vulnerability": exploit_parameters.get("vulnerability")},
            )

        account_keys = set(transaction.get("account_keys") or [])
        required_labels = config.get(
            "required_account_labels",
            [
                "wallet_address",
                "level4_state_pda",
                "market_pda",
                "position_pda",
                "mismatched_vault",
                "expected_collateral_mint",
                "mismatched_collateral_mint",
            ],
        )
        missing_labels = [
            label
            for label in required_labels
            if not challenge_context.get(label) or challenge_context.get(label) not in account_keys
        ]
        if missing_labels:
            return VerificationCheckResult(
                self.name,
                False,
                "Transaction did not include the data-matching challenge account set",
                {"missing_account_labels": missing_labels},
            )

        proof = payload.get("data_matching") or payload.get("relationship_proof") or {}
        if not isinstance(proof, dict):
            proof = {}
        route_executed = proof.get("route_executed", payload.get("route_executed"))
        mismatched_market = proof.get("mismatched_market", payload.get("mismatched_market"))
        mismatched_vault = proof.get("mismatched_vault", payload.get("mismatched_vault"))
        mismatched_mint = proof.get("mismatched_mint", payload.get("mismatched_mint"))
        mismatch_present = any(value is True for value in [mismatched_market, mismatched_vault, mismatched_mint])
        if route_executed is not True:
            return VerificationCheckResult(
                self.name,
                False,
                "Level 4 proof did not execute the vulnerable route path",
                {"route_executed": route_executed},
            )
        if not mismatch_present:
            return VerificationCheckResult(
                self.name,
                False,
                "Fully matched account relationships do not complete Level 4",
                {
                    "mismatched_market": mismatched_market,
                    "mismatched_vault": mismatched_vault,
                    "mismatched_mint": mismatched_mint,
                },
            )

        expected_vault = challenge_context.get("mismatched_vault")
        provided_vault = proof.get("provided_collateral_vault") or payload.get("provided_collateral_vault")
        if expected_vault and provided_vault and provided_vault != expected_vault:
            return VerificationCheckResult(
                self.name,
                False,
                "Provided collateral vault is not the session mismatched vault",
                {"expected": expected_vault, "actual": provided_vault},
            )

        return VerificationCheckResult(
            self.name,
            True,
            "Data matching proof accepted",
            {
                "checked_account_labels": required_labels,
                "mismatched_market": mismatched_market,
                "mismatched_vault": mismatched_vault,
                "mismatched_mint": mismatched_mint,
            },
        )


class AddressReuseLifecycleStrategy:
    name = "address_reuse_lifecycle"

    def verify(self, config: dict[str, Any], payload: dict[str, Any]) -> VerificationCheckResult:
        transaction = payload.get("onchain_transaction")
        if not isinstance(transaction, dict) or transaction.get("exists") is not True:
            return VerificationCheckResult(self.name, False, "Transaction was not found on devnet")

        challenge_context = payload.get("challenge_context") or {}
        exploit_parameters = challenge_context.get("exploit_parameters") or {}
        if exploit_parameters.get("vulnerability") != "address_reuse":
            return VerificationCheckResult(
                self.name,
                False,
                "Challenge context is not an address reuse exploit",
                {"vulnerability": exploit_parameters.get("vulnerability")},
            )

        account_keys = set(transaction.get("account_keys") or [])
        required_labels = config.get(
            "required_account_labels",
            ["wallet_address", "level5_state_pda", "receipt_pda"],
        )
        missing_labels = [
            label
            for label in required_labels
            if not challenge_context.get(label) or challenge_context.get(label) not in account_keys
        ]
        if missing_labels:
            return VerificationCheckResult(
                self.name,
                False,
                "Transaction did not include the address-reuse challenge account set",
                {"missing_account_labels": missing_labels},
            )

        proof = payload.get("address_reuse") or payload.get("lifecycle_proof") or {}
        if not isinstance(proof, dict):
            proof = {}
        receipt_pda = proof.get("receipt_pda", payload.get("receipt_pda"))
        order_id = proof.get("order_id", payload.get("order_id"))
        previous_status = str(proof.get("previous_status", payload.get("previous_status", ""))).lower()
        final_status = str(proof.get("final_status", payload.get("final_status", ""))).lower()
        address_reused = proof.get("address_reused", payload.get("address_reused"))
        reopened = proof.get("reopened", payload.get("reopened"))
        guarded_lifecycle = proof.get("guarded_lifecycle", payload.get("guarded_lifecycle"))

        if receipt_pda != challenge_context.get("receipt_pda"):
            return VerificationCheckResult(
                self.name,
                False,
                "Receipt PDA does not match the session challenge PDA",
                {"expected": challenge_context.get("receipt_pda"), "actual": receipt_pda},
            )
        if order_id != challenge_context.get("order_id"):
            return VerificationCheckResult(
                self.name,
                False,
                "Order id does not match the session challenge order",
                {"expected": challenge_context.get("order_id"), "actual": order_id},
            )
        if previous_status not in {"archived", "closed"} or final_status != "open":
            return VerificationCheckResult(
                self.name,
                False,
                "Receipt lifecycle did not transition from stale state back to open",
                {"previous_status": previous_status, "final_status": final_status},
            )
        if address_reused is not True or reopened is not True or guarded_lifecycle is True:
            return VerificationCheckResult(
                self.name,
                False,
                "Level 5 requires the stale receipt PDA address to be reused and reopened",
                {
                    "address_reused": address_reused,
                    "reopened": reopened,
                    "guarded_lifecycle": guarded_lifecycle,
                },
            )

        return VerificationCheckResult(
            self.name,
            True,
            "Address reuse lifecycle proof accepted",
            {
                "receipt_pda": receipt_pda,
                "order_id": order_id,
                "previous_status": previous_status,
                "final_status": final_status,
            },
        )


class AuthorityStrategy:
    name = "authority"

    def verify(self, config: dict[str, Any], payload: dict[str, Any]) -> VerificationCheckResult:
        actual = payload.get("authority")
        expected = config.get("expected", {})
        if not isinstance(actual, dict):
            return VerificationCheckResult(self.name, False, "Missing authority proof")
        mismatches = _collect_mismatches(expected, actual)
        if mismatches:
            return VerificationCheckResult(
                self.name,
                False,
                "Authority proof did not match expected outcome",
                {"mismatches": mismatches},
            )
        return VerificationCheckResult(self.name, True, "Authority proof accepted")


class VerificationEngine:
    def __init__(self, strategies: list[VerificationStrategy] | None = None) -> None:
        default_strategies = [
            SessionBindingStrategy(),
            ReplayProtectionStrategy(),
            TransactionSignatureStrategy(),
            SolanaTransactionStrategy(),
            PDAStateStrategy(),
            TokenBalanceStrategy(),
            PDACommanderHijackStrategy(),
            DelegatedCPIExploitStrategy(),
            DataMatchingExploitStrategy(),
            AddressReuseLifecycleStrategy(),
            AuthorityStrategy(),
        ]
        self._strategies = {
            strategy.name: strategy for strategy in strategies or default_strategies
        }

    def verify(self, config: dict[str, Any], payload: dict[str, Any]) -> VerificationResult:
        checks_config = config.get("checks", [])
        if not isinstance(checks_config, list) or not checks_config:
            return VerificationResult(False, "Level has no verification checks configured", [])

        results: list[VerificationCheckResult] = []
        for check_config in checks_config:
            check_type = check_config.get("type")
            strategy = self._strategies.get(check_type)
            if strategy is None:
                results.append(
                    VerificationCheckResult(
                        str(check_type), False, "Unsupported verification check"
                    )
                )
                continue
            results.append(strategy.verify(check_config, payload))

        verified = all(result.passed for result in results)
        message = "Verification succeeded" if verified else "Verification failed"
        return VerificationResult(verified=verified, message=message, checks=results)


def _collect_mismatches(expected: dict[str, Any], actual: dict[str, Any]) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if actual_value != expected_value:
            mismatches.append({"field": key, "expected": expected_value, "actual": actual_value})
    return mismatches
