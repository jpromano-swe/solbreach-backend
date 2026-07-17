from __future__ import annotations

import asyncio
import json
import re
import shutil
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions.domain import ConflictError, NotFoundError
from app.modules.labs.infrastructure.database.models import ResearchLabSessionModel
from app.modules.sandbox.domain.runtime import (
    SandboxAccountSnapshot,
    SandboxAccountSummary,
    SandboxRuntime,
    SandboxTerminalEvent,
    SandboxTestResult,
    SandboxTestRunResult,
    SandboxTransactionResult,
    SandboxVerificationResult,
    resolve_lab_file_path,
    resolve_lab_template_ref,
)
from app.modules.sandbox.infrastructure.yield_hijack_runtime import (
    YIELD_HIJACK_OBJECTIVE_REF,
    YIELD_HIJACK_TEMPLATE_REF,
    YieldHijackRuntime,
)

TEST_LABELS = {
    "normal_deposit_accepts_normal_oracle_input": "test deposit accepts normal oracle input",
    "overflow_shaped_oracle_input_is_rejected": (
        "test overflow-shaped oracle input is rejected"
    ),
}
OFFICIAL_COLLATERAL_REFS = {"official_collateral", "official_collateral_account"}
COUNTERFEIT_COLLATERAL_REFS = {
    "attacker_collateral",
    "attacker_collateral_account",
    "candidate_collateral",
    "candidate_collateral_account",
}
OFFICIAL_VAULT_REFS = {"official_vault", "official_vault_account"}
COUNTERFEIT_VAULT_REFS = {
    "counterfeit_vault",
    "counterfeit_vault_account",
    "external_vault",
    "external_vault_account",
}
LOCAL_LTV_BPS = 8_000
INITIAL_POOL_LIQUIDITY = 100_000
INITIAL_REWARD_LAMPORTS = 0
OFFICIAL_COLLATERAL_START = 50_000
COUNTERFEIT_COLLATERAL_START = 500_000


class LocalProcessSandboxRuntime(SandboxRuntime):
    """Backend development runtime backed by a per-session local workspace."""

    def __init__(
        self,
        template_root: Path,
        workspace_root: Path,
        db_session: AsyncSession | None = None,
    ) -> None:
        self._template_root = template_root
        self._workspace_root = workspace_root
        self._db_session = db_session

    async def create_session(self, session_id: str, template_ref: str) -> str:
        await self.hydrate_template(session_id, template_ref)
        return str(self._workspace_path(session_id))

    async def hydrate_template(self, session_id: str, template_ref: str) -> None:
        source = self._template_path(template_ref)
        if not source.exists():
            raise NotFoundError("Research lab template not found")
        destination = self._workspace_path(session_id)
        if destination.exists():
            shutil.rmtree(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination)
        if resolve_lab_template_ref(template_ref) == "research-labs/treasury-mirage@v1":
            self._write_state(session_id, _initial_treasury_mirage_state())

    async def read_file(self, session_id: str, path: str) -> str:
        if await self._is_yield_hijack_session(session_id):
            return await self._yield_hijack_runtime().read_file(path)
        file_path = self._safe_file_path(session_id, path)
        if not file_path.exists() or not file_path.is_file():
            raise NotFoundError("Sandbox file not found")
        return file_path.read_text(encoding="utf-8")

    async def patch_file(self, session_id: str, path: str, content: str) -> None:
        file_path = self._safe_file_path(session_id, path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

    async def run_tests(
        self, session_id: str, command: str, timeout_seconds: int
    ) -> SandboxTestRunResult:
        workspace = self._workspace_path(session_id)
        if not workspace.exists():
            raise ConflictError("Sandbox session is not ready")

        terminal = [
            SandboxTerminalEvent("system", f"$ {command}"),
        ]
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=workspace,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout_seconds
            )
        except TimeoutError:
            return SandboxTestRunResult(
                status="timeout",
                exit_code=None,
                terminal_events=[
                    *terminal,
                    SandboxTerminalEvent("system", "Test run timed out."),
                ],
                results=_results_from_output("", timed_out=True),
            )

        stdout_text = stdout.decode("utf-8", errors="replace")
        stderr_text = stderr.decode("utf-8", errors="replace")
        terminal.extend(_terminal_events("stdout", stdout_text))
        terminal.extend(_terminal_events("stderr", stderr_text))
        output = f"{stdout_text}\n{stderr_text}"
        status = "passed" if process.returncode == 0 else "failed"
        return SandboxTestRunResult(
            status=status,
            exit_code=process.returncode,
            terminal_events=terminal,
            results=_results_from_output(output, all_passed=status == "passed"),
        )

    async def reset_session(self, session_id: str, template_ref: str) -> None:
        await self.hydrate_template(session_id, template_ref)

    async def destroy_session(self, session_id: str) -> None:
        workspace = self._workspace_path(session_id)
        if workspace.exists():
            shutil.rmtree(workspace)

    async def get_visible_accounts(self, session_id: str) -> list[SandboxAccountSummary]:
        if await self._is_yield_hijack_session(session_id):
            return await self._yield_hijack_runtime().get_visible_accounts(session_id)
        state = self._read_state(session_id)
        return [
            SandboxAccountSummary(
                ref=ref,
                label=account["label"],
                owner=account["owner"],
                lamports=account["lamports"],
                data=_learner_safe_data(account["data"]),
            )
            for ref, account in state["accounts"].items()
            if account["visible"]
        ]

    async def get_account_state(
        self, session_id: str, account_ref: str
    ) -> SandboxAccountSnapshot:
        if await self._is_yield_hijack_session(session_id):
            return await self._yield_hijack_runtime().get_account_state(
                session_id, account_ref
            )
        state = self._read_state(session_id)
        storage_ref = "attacker_position" if account_ref == "position" else account_ref
        account = state["accounts"].get(storage_ref)
        if account is None or not account["visible"]:
            raise NotFoundError("Sandbox account not found")
        data = (
            _local_protocol_state(state)
            if storage_ref == "attacker_position"
            else _learner_safe_data(account["data"])
        )
        return SandboxAccountSnapshot(
            ref=account_ref,
            label=account["label"],
            owner=account["owner"],
            lamports=account["lamports"],
            data=data,
        )

    async def submit_transaction(
        self, session_id: str, action_type: str, parameters: dict
    ) -> SandboxTransactionResult:
        if await self._is_yield_hijack_session(session_id):
            return await self._yield_hijack_runtime().submit_transaction(
                session_id, action_type, parameters
            )
        state = self._read_state(session_id)
        if state["lab_slug"] != "account-substitution":
            raise ConflictError("Sandbox transactions are not configured for this lab")

        tx_ref = f"tx_{uuid4().hex[:16]}"
        before = deepcopy(state)
        logs: list[str]
        evidence: list[str] = []
        status = "success"
        rejection = None
        if action_type in {"deposit_counterfeit_collateral", "DEPOSIT_COLLATERAL"}:
            collateral_ref = parameters.get("collateral_account_ref")
            vault_ref = parameters.get("vault_account_ref")
            rejection = _deposit_rejection(collateral_ref, vault_ref)
            if rejection is not None:
                status = "failure"
                logs = ["Transaction submitted to SVM.", rejection["log"]]
                evidence = [{"type": "rejected_transaction", "summary": rejection["summary"]}]
            else:
                status, logs, evidence = _deposit_collateral(
                    state, collateral_ref, vault_ref, parameters
                )
        elif action_type in {"withdraw_treasury_credit", "WITHDRAW_AGAINST_CREDIT"}:
            status, logs, evidence = _withdraw_treasury_credit(state, parameters)
        else:
            status = "failure"
            logs = [f"Unsupported sandbox action: {action_type}"]

        state["transactions"][tx_ref] = {
            "transaction_ref": tx_ref,
            "instruction_type": action_type,
            "execution_status": status,
            "logs": logs,
            "parameters": parameters,
        }
        self._write_state(session_id, state)
        return SandboxTransactionResult(
            transaction_ref=tx_ref,
            instruction_type=action_type,
            execution_status=status,
            logs=logs,
            account_deltas=_local_account_deltas(before, state) if status == "success" else [],
            protocol_state=_local_protocol_state(state, rejection),
            user_facing_evidence=evidence,
        )

    async def get_transaction_logs(self, session_id: str, transaction_ref: str) -> list[str]:
        state = self._read_state(session_id)
        transaction = state["transactions"].get(transaction_ref)
        if transaction is None:
            raise NotFoundError("Sandbox transaction not found")
        return list(transaction["logs"])

    async def verify_objective(
        self, session_id: str, objective_ref: str
    ) -> SandboxVerificationResult:
        if await self._is_yield_hijack_session(session_id):
            if objective_ref != YIELD_HIJACK_OBJECTIVE_REF:
                raise NotFoundError("Sandbox objective not found")
            return await self._yield_hijack_runtime().verify_objective(
                session_id, objective_ref
            )
        state = self._read_state(session_id)
        if objective_ref != "RL1_ACCOUNT_SUBSTITUTION_IMPACT":
            raise NotFoundError("Sandbox objective not found")
        position = state["accounts"]["attacker_position"]["data"]
        treasury = state["accounts"]["treasury_vault"]
        reward = state["accounts"]["attacker_reward_account"]
        protocol_state = _local_protocol_state(state)
        transactions = list(state["transactions"].values())
        successful_exploit_deposit = None
        successful_official_deposit = None
        successful_withdrawal = None
        for transaction in transactions:
            if transaction.get("execution_status") != "success":
                continue
            params = transaction.get("parameters") or {}
            if transaction.get("instruction_type") == "DEPOSIT_COLLATERAL":
                path_type = _deposit_path_type(
                    params.get("collateral_account_ref"),
                    params.get("vault_account_ref"),
                )
                if path_type == "exploit":
                    successful_exploit_deposit = transaction
                elif path_type == "official":
                    successful_official_deposit = transaction
            elif transaction.get("instruction_type") == "WITHDRAW_AGAINST_CREDIT":
                successful_withdrawal = transaction

        borrowed_total = int(protocol_state["borrowedTotal"])
        available_borrow = int(protocol_state["availableBorrow"])
        max_drain_satisfied = bool(protocol_state["maxDrainSatisfied"])
        passed = (
            successful_exploit_deposit is not None
            and successful_withdrawal is not None
            and position["counterfeit_collateral_deposited"] is True
            and position["illegitimate_credit"] > 0
            and treasury["lamports"] < state["initial_treasury_lamports"]
            and reward["lamports"] > state["initial_reward_lamports"]
            and bool(protocol_state["hasExploitDeposit"])
            and max_drain_satisfied
        )
        evidence = {
            "counterfeitAssetDeposited": position["counterfeit_collateral_deposited"],
            "illegitimateCreditAssigned": position["illegitimate_credit"] > 0,
            "legitimateTreasuryValueWithdrawn": (
                treasury["lamports"] < state["initial_treasury_lamports"]
            ),
            "sessionOwnershipValid": True,
            "transactionTimeline": [
                {
                    "transactionRef": ref,
                    "instructionType": transaction["instruction_type"],
                    "executionStatus": transaction["execution_status"],
                    "sequenceNumber": index,
                }
                for index, (ref, transaction) in enumerate(state["transactions"].items(), start=1)
            ],
            "runtimeLogs": [
                {"transactionRef": ref, "logs": transaction["logs"]}
                for ref, transaction in state["transactions"].items()
            ],
            "impactChecklist": {
                "counterfeitDepositObserved": successful_exploit_deposit is not None,
                "unapprovedCollateralSourceUsed": successful_exploit_deposit is not None,
                "nonCanonicalVaultDestinationUsed": successful_exploit_deposit is not None,
                "positionCreditIncreasedFromInvalidRelationship": (
                    successful_exploit_deposit is not None and position["illegitimate_credit"] > 0
                ),
                "withdrawOrBorrowAgainstInvalidCreditObserved": successful_withdrawal is not None,
                "realProtocolTreasuryValueDecreased": treasury["lamports"] < state["initial_treasury_lamports"],
                "exploitProvenanceConfirmed": (
                    successful_exploit_deposit is not None and successful_withdrawal is not None
                ),
                "officialPathUsed": successful_official_deposit is not None,
                "exploitPathOnly": bool(protocol_state["hasExploitDeposit"]),
                "hasOfficialDeposit": bool(protocol_state["hasOfficialDeposit"]),
                "hasExploitDeposit": bool(protocol_state["hasExploitDeposit"]),
                "maxDrainSatisfied": max_drain_satisfied,
            },
            "protocolState": protocol_state,
            "borrowedAmount": borrowed_total,
            "maxBorrowAmount": protocol_state["maxBorrow"],
            "availableBorrowAfter": available_borrow,
        }
        failure_reason = None
        if not passed:
            if successful_exploit_deposit is None:
                failure_reason = "No invalid collateral-to-vault deposit has been observed."
            elif successful_withdrawal is None:
                failure_reason = "No treasury withdrawal against invalid credit has been observed."
            elif not bool(protocol_state["hasExploitDeposit"]):
                failure_reason = "No exploit-path collateral deposit has been observed."
            elif not max_drain_satisfied:
                failure_reason = (
                    "Exploit path was used, but the pool was not drained to the backend-computed "
                    f"max executable amount ({protocol_state['maxDrainAmount']})."
                )
        return SandboxVerificationResult(
            objective_ref=objective_ref,
            passed=passed,
            evidence=evidence,
            verified_evidence_refs=(
                [f"transaction:{successful_exploit_deposit['transaction_ref']}", f"transaction:{successful_withdrawal['transaction_ref']}", "account:treasury_vault"]
                if passed and successful_exploit_deposit is not None and successful_withdrawal is not None
                else []
            ),
            failure_reason=failure_reason,
            user_facing_evidence=(
                [
                    "Unauthorized protocol state transition confirmed.",
                    "Treasury value reached the attacker reward account.",
                    "You may now submit a finding report.",
                ]
                if passed
                else [failure_reason or "Objective impact has not been proven yet."]
            ),
        )

    def _template_path(self, template_ref: str) -> Path:
        return self._template_root / resolve_lab_template_ref(template_ref)

    def _workspace_path(self, session_id: str) -> Path:
        return self._workspace_root / session_id

    def _safe_file_path(self, session_id: str, path: str) -> Path:
        workspace = self._workspace_path(session_id).resolve()
        candidate = (workspace / resolve_lab_file_path(path)).resolve()
        if workspace not in candidate.parents and candidate != workspace:
            raise ConflictError("Invalid file path")
        return candidate

    def _state_path(self, session_id: str) -> Path:
        return self._workspace_path(session_id) / ".solbreach_sandbox_state.json"

    def _read_state(self, session_id: str) -> dict:
        state_path = self._state_path(session_id)
        if not state_path.exists():
            raise ConflictError("Sandbox state is not available for this session")
        return json.loads(state_path.read_text(encoding="utf-8"))

    def _write_state(self, session_id: str, state: dict) -> None:
        state_path = self._state_path(session_id)
        state_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")

    def _yield_hijack_runtime(self) -> YieldHijackRuntime:
        if self._db_session is None:
            raise ConflictError("Sandbox state is not available for this session")
        return YieldHijackRuntime(self._template_root, self._db_session)

    async def _is_yield_hijack_session(self, session_id: str) -> bool:
        if self._db_session is None:
            return False
        session = await self._db_session.get(ResearchLabSessionModel, session_id)
        return session is not None and session.template_ref == YIELD_HIJACK_TEMPLATE_REF


def _terminal_events(stream: str, text: str) -> list[SandboxTerminalEvent]:
    return [
        SandboxTerminalEvent(stream=stream, line=line)
        for line in text.splitlines()
        if line.strip()
    ]


def _results_from_output(
    output: str, *, all_passed: bool = False, timed_out: bool = False
) -> list[SandboxTestResult]:
    results: list[SandboxTestResult] = []
    for test_id, label in TEST_LABELS.items():
        if all_passed:
            passed = True
            details = None
        elif timed_out:
            passed = False
            details = "Test run timed out before completion."
        else:
            passed = _test_passed(output, test_id)
            details = None if passed else "Test did not pass in the sandbox run."
        results.append(SandboxTestResult(id=test_id, label=label, passed=passed, details=details))
    return results


def _test_passed(output: str, test_id: str) -> bool:
    ok_pattern = re.compile(rf"test .*{re.escape(test_id)}.* \.\.\. ok")
    return bool(ok_pattern.search(output))


def _initial_treasury_mirage_state() -> dict:
    return {
        "lab_slug": "account-substitution",
        "initial_treasury_lamports": INITIAL_POOL_LIQUIDITY,
        "initial_reward_lamports": INITIAL_REWARD_LAMPORTS,
        "transactions": {},
        "accounts": {
            "treasury_vault": {
                "label": "Treasury Vault",
                "owner": "TreasuryMirageProgram",
                "lamports": INITIAL_POOL_LIQUIDITY,
                "visible": True,
                "data": {"asset": "LEGIT", "authority": "vault_authority"},
            },
            "accepted_collateral_mint": {
                "label": "Accepted Collateral Mint",
                "owner": "TokenProgram",
                "lamports": 0,
                "visible": True,
                "data": {"symbol": "sUSDC", "approved": True},
            },
            "counterfeit_collateral_mint": {
                "label": "Counterfeit Collateral Mint",
                "owner": "TokenProgram",
                "lamports": 0,
                "visible": True,
                "data": {"symbol": "fUSDC", "approved": False},
            },
            "attacker_collateral_account": {
                "label": "Attacker Collateral Account",
                "owner": "TokenProgram",
                "lamports": 0,
                "visible": True,
                "data": {
                    "mint": "counterfeit_collateral_mint",
                    "amount": 500_000,
                    "authority": "attacker_wallet",
                },
            },
            "official_collateral_account": {
                "label": "Official Collateral Account",
                "owner": "TokenProgram",
                "lamports": 0,
                "visible": True,
                "data": {
                    "mint": "accepted_collateral_mint",
                    "amount": OFFICIAL_COLLATERAL_START,
                    "authority": "attacker_wallet",
                },
            },
            "counterfeit_vault_account": {
                "label": "External Vault",
                "owner": "TokenProgram",
                "lamports": 0,
                "visible": True,
                "data": {"mint": "counterfeit_collateral_mint", "amount": 0, "approved": False},
            },
            "official_vault_account": {
                "label": "Official Vault",
                "owner": "TokenProgram",
                "lamports": 0,
                "visible": True,
                "data": {"mint": "accepted_collateral_mint", "amount": 1_000_000, "approved": True},
            },
            "attacker_position": {
                "label": "Attacker Position",
                "owner": "TreasuryMirageProgram",
                "lamports": 0,
                "visible": True,
                "data": {
                    "credited_collateral": 0,
                    "official_collateral": OFFICIAL_COLLATERAL_START,
                    "counterfeit_collateral": 0,
                    "illegitimate_credit": 0,
                    "counterfeit_collateral_deposited": False,
                    "deposit_path_type": "none",
                    "has_official_deposit": False,
                    "has_exploit_deposit": False,
                    "borrowed_total": 0,
                },
            },
            "attacker_reward_account": {
                "label": "Attacker Reward Account",
                "owner": "SystemProgram",
                "lamports": 0,
                "visible": True,
                "data": {"authority": "attacker_wallet"},
            },
        },
    }


def _learner_safe_data(data: dict) -> dict:
    return deepcopy(data)


def _deposit_rejection(collateral_ref: str | None, vault_ref: str | None) -> dict | None:
    if collateral_ref in OFFICIAL_COLLATERAL_REFS and vault_ref in COUNTERFEIT_VAULT_REFS:
        return {
            "reason": "CANONICAL_USDC_ATTACK_VAULT",
            "log": "Transaction rejected: canonical USDC deposits must target the official protocol vault.",
            "summary": "SVM rejected the deposit because canonical USDC was routed to an attacker-controlled vault.",
        }
    if collateral_ref in COUNTERFEIT_COLLATERAL_REFS and vault_ref in OFFICIAL_VAULT_REFS:
        return {
            "reason": "COLLATERAL_VAULT_MISMATCH",
            "log": "Transaction rejected: collateral source mint does not match the official USDC vault.",
            "summary": "SVM rejected the deposit because the collateral source did not match the target vault.",
        }
    return None


def _deposit_path_type(collateral_ref: str | None, vault_ref: str | None) -> str:
    if collateral_ref in OFFICIAL_COLLATERAL_REFS and vault_ref in OFFICIAL_VAULT_REFS:
        return "official"
    if collateral_ref in COUNTERFEIT_COLLATERAL_REFS and vault_ref in COUNTERFEIT_VAULT_REFS:
        return "exploit"
    return "mixed"


def _positive_amount(parameters: dict, default: int) -> int:
    amount = int(parameters.get("amount") or default)
    return max(amount, 0)


def _local_deposit_path_type(position: dict) -> str:
    has_official = bool(position.get("has_official_deposit"))
    has_exploit = bool(position.get("has_exploit_deposit"))
    if has_official and has_exploit:
        return "mixed"
    if has_official:
        return "official"
    if has_exploit:
        return "exploit"
    return "none"


def _deposit_collateral(
    state: dict, collateral_ref: str | None, vault_ref: str | None, parameters: dict
) -> tuple[str, list[str], list]:
    logs = ["Instruction: deposit_collateral"]
    position = state["accounts"]["attacker_position"]
    if collateral_ref in COUNTERFEIT_COLLATERAL_REFS and vault_ref in COUNTERFEIT_VAULT_REFS:
        amount = COUNTERFEIT_COLLATERAL_START
        parameters["executed_amount"] = amount
        position["data"]["credited_collateral"] += amount
        position["data"]["illegitimate_credit"] += amount
        position["data"]["counterfeit_collateral"] += amount
        position["data"]["counterfeit_collateral_deposited"] = True
        position["data"]["has_exploit_deposit"] = True
        position["data"]["deposit_path_type"] = _local_deposit_path_type(position["data"])
        logs.extend(
            [
                "Program log: accepted collateral account without checking mint.",
                f"Program log: credited position with {amount} collateral units.",
            ]
        )
        return "success", logs, [
            {"type": "transaction_result", "summary": "Counterfeit collateral was accepted and credited."}
        ]

    if collateral_ref in OFFICIAL_COLLATERAL_REFS and vault_ref in OFFICIAL_VAULT_REFS:
        amount = _positive_amount(parameters, 0)
        if amount <= 0:
            logs.extend(["Collateral account rejected: deposit amount must be positive."])
            return "failure", logs, [
                {"type": "rejected_transaction", "summary": "Deposit amount must be positive."}
            ]
        position["data"]["credited_collateral"] += amount
        position["data"]["official_collateral"] += amount
        position["data"]["has_official_deposit"] = True
        position["data"]["deposit_path_type"] = _local_deposit_path_type(position["data"])
        state["accounts"]["treasury_vault"]["lamports"] += amount
        logs.extend(
            [
                "Program log: accepted canonical collateral into official vault.",
                f"Program log: credited position with {amount} collateral units.",
            ]
        )
        return "success", logs, [
            {"type": "transaction_result", "summary": "Official collateral was accepted and credited."}
        ]

    logs.extend(["Collateral account rejected: account ref not found in this session."])
    return "failure", logs, [
        {"type": "rejected_transaction", "summary": "Unknown or invalid action parameters."}
    ]


def _withdraw_treasury_credit(state: dict, parameters: dict) -> tuple[str, list[str], list]:
    logs = ["Instruction: withdraw_against_credit"]
    position = state["accounts"]["attacker_position"]
    protocol_state = _local_protocol_state(state)
    max_drain = int(protocol_state["maxDrainAmount"])
    requested_amount = int(parameters.get("amount") or max_drain)
    amount = min(requested_amount, max_drain)
    if max_drain <= 0 or amount <= 0:
        logs.append("Program log: withdrawal rejected because no position credit exists.")
        return "failure", logs, [
            {
                "type": "rejected_transaction",
                "summary": "Borrow request exceeds the currently available borrow limit.",
            }
        ]

    treasury = state["accounts"]["treasury_vault"]
    reward = state["accounts"]["attacker_reward_account"]
    parameters["executed_amount"] = amount
    treasury["lamports"] -= amount
    reward["lamports"] += amount
    position["data"]["borrowed_total"] += amount
    logs.extend(
        [
            "Program log: position credit accepted for treasury withdrawal.",
            f"Program log: transferred {amount} lamports to attacker reward account.",
        ]
    )
    return "success", logs, [
        {"type": "transaction_result", "summary": "Treasury value moved into the attacker reward account."}
    ]


def _local_protocol_state(state: dict, rejection: dict | None = None) -> dict:
    position = state["accounts"]["attacker_position"]["data"]
    treasury = state["accounts"]["treasury_vault"]
    reward = state["accounts"]["attacker_reward_account"]
    official_collateral = int(position.get("official_collateral", OFFICIAL_COLLATERAL_START) or 0)
    counterfeit_collateral = int(position.get("counterfeit_collateral", 0) or 0)
    credited_collateral = official_collateral + counterfeit_collateral
    borrowed_total = int(position.get("borrowed_total", 0) or 0)
    max_borrow = (credited_collateral * LOCAL_LTV_BPS) // 10_000
    available_borrow = max(max_borrow - borrowed_total, 0)
    pool_liquidity = int(treasury["lamports"])
    max_drain_amount = min(available_borrow, pool_liquidity)
    protocol_state = {
        "depositPathType": _local_deposit_path_type(position),
        "officialCollateral": official_collateral,
        "counterfeitCollateral": counterfeit_collateral,
        "creditedCollateral": credited_collateral,
        "effectiveCreditedCollateral": credited_collateral,
        "poolLiquidity": pool_liquidity,
        "treasuryLamports": pool_liquidity,
        "initialTreasuryLamports": int(state["initial_treasury_lamports"]),
        "rewardLamports": int(reward["lamports"]),
        "successfulDeposits": [],
        "successfulWithdrawals": [],
        "maxBorrow": max_borrow,
        "availableBorrow": available_borrow,
        "maxDrainAmount": max_drain_amount,
        "borrowedTotal": borrowed_total,
        "borrowAllowed": available_borrow > 0 and pool_liquidity > 0,
        "ltvBps": LOCAL_LTV_BPS,
        "hasOfficialDeposit": bool(position.get("has_official_deposit")),
        "hasExploitDeposit": bool(position.get("has_exploit_deposit")),
        "maxDrainSatisfied": pool_liquidity == 0 and borrowed_total > 0,
    }
    if rejection is not None:
        protocol_state["lastRejectedReason"] = rejection["reason"]
    return protocol_state


def _local_account_deltas(before: dict, after: dict) -> list[dict]:
    deltas: list[dict] = []
    account_refs = sorted(set(before["accounts"]) | set(after["accounts"]))
    for ref in account_refs:
        previous = before["accounts"].get(ref, {})
        current = after["accounts"].get(ref, {})
        before_lamports = int(previous.get("lamports", 0) or 0)
        after_lamports = int(current.get("lamports", 0) or 0)
        before_value = _local_account_value(previous)
        after_value = _local_account_value(current)
        if before_lamports == after_lamports and before_value == after_value:
            continue
        deltas.append(
            {
                "accountRef": "position" if ref == "attacker_position" else ref,
                "label": current.get("label") or previous.get("label") or ref,
                "lamportsBefore": before_lamports,
                "lamportsAfter": after_lamports,
                "lamportsDelta": after_lamports - before_lamports,
                "valueBefore": before_value,
                "valueAfter": after_value,
                "valueDelta": after_value - before_value,
            }
        )
    return deltas


def _local_account_value(account: dict) -> int:
    data = account.get("data") or {}
    if "official_collateral" in data or "counterfeit_collateral" in data:
        return int(data.get("official_collateral", 0) or 0) + int(
            data.get("counterfeit_collateral", 0) or 0
        )
    if "amount" in data:
        return int(data.get("amount", 0) or 0)
    return 0
