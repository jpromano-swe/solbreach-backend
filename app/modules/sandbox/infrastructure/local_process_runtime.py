from __future__ import annotations

import asyncio
import json
import re
import shutil
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from app.core.exceptions.domain import ConflictError, NotFoundError
from app.modules.sandbox.domain.runtime import (
    SandboxAccountSnapshot,
    SandboxAccountSummary,
    SandboxRuntime,
    SandboxTerminalEvent,
    SandboxTestResult,
    SandboxTestRunResult,
    SandboxTransactionResult,
    SandboxVerificationResult,
)

TEST_LABELS = {
    "normal_deposit_accepts_normal_oracle_input": "test deposit accepts normal oracle input",
    "overflow_shaped_oracle_input_is_rejected": (
        "test overflow-shaped oracle input is rejected"
    ),
}


class LocalProcessSandboxRuntime(SandboxRuntime):
    """Backend development runtime backed by a per-session local workspace."""

    def __init__(self, template_root: Path, workspace_root: Path) -> None:
        self._template_root = template_root
        self._workspace_root = workspace_root

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
        if template_ref == "research-labs/treasury-mirage@v1":
            self._write_state(session_id, _initial_treasury_mirage_state())

    async def read_file(self, session_id: str, path: str) -> str:
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
        state = self._read_state(session_id)
        account = state["accounts"].get(account_ref)
        if account is None or not account["visible"]:
            raise NotFoundError("Sandbox account not found")
        return SandboxAccountSnapshot(
            ref=account_ref,
            label=account["label"],
            owner=account["owner"],
            lamports=account["lamports"],
            data=_learner_safe_data(account["data"]),
        )

    async def submit_transaction(
        self, session_id: str, action_type: str, parameters: dict
    ) -> SandboxTransactionResult:
        state = self._read_state(session_id)
        if state["lab_slug"] != "treasury-mirage":
            raise ConflictError("Sandbox transactions are not configured for this lab")

        tx_ref = f"tx_{uuid4().hex[:16]}"
        logs: list[str]
        evidence: list[str] = []
        status = "success"
        if action_type == "deposit_counterfeit_collateral":
            collateral_ref = parameters.get("collateral_account_ref")
            logs, evidence = _deposit_counterfeit_collateral(state, collateral_ref)
        elif action_type == "withdraw_treasury_credit":
            logs, evidence = _withdraw_treasury_credit(state)
        else:
            status = "failure"
            logs = [f"Unsupported sandbox action: {action_type}"]

        state["transactions"][tx_ref] = {
            "transaction_ref": tx_ref,
            "instruction_type": action_type,
            "execution_status": status,
            "logs": logs,
        }
        self._write_state(session_id, state)
        return SandboxTransactionResult(
            transaction_ref=tx_ref,
            instruction_type=action_type,
            execution_status=status,
            logs=logs,
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
        state = self._read_state(session_id)
        if objective_ref != "RL1_UNAUTHORIZED_TREASURY_WITHDRAWAL":
            raise NotFoundError("Sandbox objective not found")
        position = state["accounts"]["attacker_position"]["data"]
        treasury = state["accounts"]["treasury_vault"]
        reward = state["accounts"]["attacker_reward_account"]
        passed = (
            position["counterfeit_collateral_deposited"] is True
            and position["illegitimate_credit"] > 0
            and treasury["lamports"] < state["initial_treasury_lamports"]
            and reward["lamports"] > state["initial_reward_lamports"]
        )
        evidence = {
            "counterfeitAssetDeposited": position["counterfeit_collateral_deposited"],
            "illegitimateCreditAssigned": position["illegitimate_credit"] > 0,
            "legitimateTreasuryValueWithdrawn": (
                treasury["lamports"] < state["initial_treasury_lamports"]
            ),
            "sessionOwnershipValid": True,
        }
        return SandboxVerificationResult(
            objective_ref=objective_ref,
            passed=passed,
            evidence=evidence,
            user_facing_evidence=(
                [
                    "Unauthorized protocol state transition confirmed.",
                    "Treasury value reached the attacker reward account.",
                    "You may now submit a finding report.",
                ]
                if passed
                else ["Objective impact has not been proven yet."]
            ),
        )

    def _template_path(self, template_ref: str) -> Path:
        return self._template_root / template_ref

    def _workspace_path(self, session_id: str) -> Path:
        return self._workspace_root / session_id

    def _safe_file_path(self, session_id: str, path: str) -> Path:
        workspace = self._workspace_path(session_id).resolve()
        candidate = (workspace / path).resolve()
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
        "lab_slug": "treasury-mirage",
        "initial_treasury_lamports": 1_000_000,
        "initial_reward_lamports": 0,
        "transactions": {},
        "accounts": {
            "treasury_vault": {
                "label": "Treasury Vault",
                "owner": "TreasuryMirageProgram",
                "lamports": 1_000_000,
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
            "attacker_position": {
                "label": "Attacker Position",
                "owner": "TreasuryMirageProgram",
                "lamports": 0,
                "visible": True,
                "data": {
                    "credited_collateral": 0,
                    "illegitimate_credit": 0,
                    "counterfeit_collateral_deposited": False,
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


def _deposit_counterfeit_collateral(
    state: dict, collateral_ref: str | None
) -> tuple[list[str], list[str]]:
    logs = ["Instruction: deposit_collateral"]
    if collateral_ref != "attacker_collateral_account":
        logs.extend(["Collateral account rejected: account ref not found in this session."])
        return logs, []

    collateral = state["accounts"]["attacker_collateral_account"]
    position = state["accounts"]["attacker_position"]
    amount = int(collateral["data"]["amount"])
    position["data"]["credited_collateral"] += amount
    position["data"]["illegitimate_credit"] += amount
    position["data"]["counterfeit_collateral_deposited"] = True
    logs.extend(
        [
            "Program log: accepted collateral account without checking mint.",
            f"Program log: credited position with {amount} collateral units.",
        ]
    )
    return logs, ["Counterfeit collateral was accepted and credited."]


def _withdraw_treasury_credit(state: dict) -> tuple[list[str], list[str]]:
    logs = ["Instruction: withdraw_against_credit"]
    position = state["accounts"]["attacker_position"]
    if int(position["data"]["illegitimate_credit"]) <= 0:
        logs.append("Program log: withdrawal rejected because no position credit exists.")
        return logs, []

    treasury = state["accounts"]["treasury_vault"]
    reward = state["accounts"]["attacker_reward_account"]
    amount = 250_000
    treasury["lamports"] -= amount
    reward["lamports"] += amount
    logs.extend(
        [
            "Program log: position credit accepted for treasury withdrawal.",
            f"Program log: transferred {amount} lamports to attacker reward account.",
        ]
    )
    return logs, ["Treasury value moved into the attacker reward account."]
