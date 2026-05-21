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
            TransactionSignatureStrategy(),
            PDAStateStrategy(),
            TokenBalanceStrategy(),
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
