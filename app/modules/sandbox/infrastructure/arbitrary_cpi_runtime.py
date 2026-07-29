from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from solders.keypair import Keypair
from solders.pubkey import Pubkey

from app.core.config.settings import get_settings
from app.core.exceptions.domain import ConflictError, NotFoundError
from app.modules.labs.infrastructure.database.models import ResearchLabTransactionModel
from app.modules.sandbox.domain.runtime import (
    SandboxAccountSnapshot,
    SandboxAccountSummary,
    SandboxExplorerSnapshot,
    SandboxTransactionResult,
    SandboxVerificationResult,
    resolve_lab_file_path,
)

ARBITRARY_CPI_TEMPLATE_REF = "research-labs/arbitrary-cpi@v1"
ARBITRARY_CPI_OBJECTIVE_REF = "RL3_ARBITRARY_CPI_BOUNTY_DRAIN_IMPACT"
CANONICAL_EXECUTE_DELEGATED_PAYOUT = "execute_delegated_payout"

BOUNTY_TOTAL_ESCROWED = 100_000
TASK_REWARD_AMOUNT = 75_000
ATTACKER_PROGRAM_ARTIFACT_REF = "attacker_program_build"
ATTACKER_PROGRAM_REF = "attacker_cpi_program"
ATTACKER_PROGRAM_TEMPLATE = "cpi_drain_router"
ATTACKER_ENTRYPOINT = "execute"
ATTACKER_AUTHORITY_STRATEGY = "reuse_delegated_signer"
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
SYSTEM_PROGRAM_ID = "11111111111111111111111111111111"

RL3_ACCOUNT_LABELS = {
    "bounty_config": "Bounty Configuration",
    "bounty_authority": "Bounty Authority",
    "bounty_vault": "Bounty Vault",
    "task_record": "Task Record",
    "task_escrow": "Task Escrow",
    "official_payout_router": "Official Payout Router",
    "approved_worker_account": "Approved Worker Account",
    "attacker_reward_account": "Attacker Reward Account",
    "attacker_program_buffer": "Attacker Program Buffer",
    ATTACKER_PROGRAM_REF: "Attacker CPI Program",
}

BASE_VISIBLE_REFS = [
    "bounty_config",
    "bounty_authority",
    "bounty_vault",
    "task_record",
    "task_escrow",
    "official_payout_router",
    "approved_worker_account",
    "attacker_reward_account",
    "attacker_program_buffer",
]


@dataclass(slots=True)
class ArbitraryCPIState:
    bounty_pool: dict
    task: dict
    user: dict
    attacker: dict
    cpi: dict
    successful_builds: list[dict]
    successful_deployments: list[dict]
    successful_delegations: list[dict]
    successful_executions: list[dict]
    failed_transactions: list[dict]


class ArbitraryCPIMaterializer:
    def __init__(self, template_root: Path, db_session: AsyncSession, session_id: str) -> None:
        self.template_root = template_root
        self.db_session = db_session
        self.session_id = session_id
        settings = get_settings()
        self._secret = (settings.jwt_secret_key or "dev_secret_key").encode()

        self.program_id = self._derive_keypair("task_bounty_program").pubkey()
        self.attacker_wallet = self._derive_keypair("attacker_wallet").pubkey()
        self.bounty_config = self._derive_keypair("bounty_config").pubkey()
        self.bounty_vault = self._derive_keypair("bounty_vault").pubkey()
        self.task_record = self._derive_keypair("task_record").pubkey()
        self.task_escrow = self._derive_keypair("task_escrow").pubkey()
        self.official_payout_router = self._derive_keypair("official_payout_router").pubkey()
        self.approved_worker_account = self._derive_keypair("approved_worker_account").pubkey()
        self.attacker_reward_account = self._derive_keypair("attacker_reward_account").pubkey()
        self.attacker_program_buffer = self._derive_keypair("attacker_program_buffer").pubkey()
        attacker_program_seed = hashlib.sha256(
            f"attacker_program|{self.session_id}".encode()
        ).digest()
        self.attacker_program_address, _ = Pubkey.find_program_address(
            [b"attacker_program", attacker_program_seed], self.program_id
        )
        self.bounty_authority, _ = Pubkey.find_program_address(
            [b"bounty_authority", bytes(self.bounty_config)], self.program_id
        )

    def _derive_keypair(self, role: str) -> Keypair:
        msg = f"arbitrary-cpi|v1|{self.session_id}|{role}".encode()
        return Keypair.from_seed(hmac.new(self._secret, msg, hashlib.sha256).digest()[:32])

    def account_pubkeys(self, state: ArbitraryCPIState | None = None) -> dict[str, Pubkey]:
        pubkeys = {
            "bounty_config": self.bounty_config,
            "bounty_authority": self.bounty_authority,
            "bounty_vault": self.bounty_vault,
            "task_record": self.task_record,
            "task_escrow": self.task_escrow,
            "official_payout_router": self.official_payout_router,
            "approved_worker_account": self.approved_worker_account,
            "attacker_reward_account": self.attacker_reward_account,
            "attacker_program_buffer": self.attacker_program_buffer,
        }
        if state is not None and state.attacker["programDeployed"]:
            pubkeys[ATTACKER_PROGRAM_REF] = self.attacker_program_address
        return pubkeys

    async def successful_transactions(self) -> list[ResearchLabTransactionModel]:
        result = await self.db_session.execute(
            select(ResearchLabTransactionModel)
            .where(ResearchLabTransactionModel.session_id == self.session_id)
            .where(ResearchLabTransactionModel.execution_status == "success")
            .order_by(ResearchLabTransactionModel.sequence_number.asc())
        )
        return list(result.scalars().all())

    async def all_transactions(self) -> list[ResearchLabTransactionModel]:
        result = await self.db_session.execute(
            select(ResearchLabTransactionModel)
            .where(ResearchLabTransactionModel.session_id == self.session_id)
            .order_by(ResearchLabTransactionModel.sequence_number.asc())
        )
        return list(result.scalars().all())

    async def state(
        self,
        extra_successful: list[ResearchLabTransactionModel | SimpleNamespace] | None = None,
    ) -> ArbitraryCPIState:
        tx_models: list[ResearchLabTransactionModel | SimpleNamespace] = [
            *await self.successful_transactions(),
            *(extra_successful or []),
        ]
        return self.state_from_successful(
            tx_models, failed_transactions=await self._failed_transactions()
        )

    def state_from_successful(
        self,
        tx_models: list[ResearchLabTransactionModel | SimpleNamespace],
        *,
        failed_transactions: list[dict] | None = None,
    ) -> ArbitraryCPIState:
        program_built = False
        program_deployed = False
        normal_delegation_submitted = False
        executed_target: str | None = None
        delegated_program = "official_payout_router"
        task_status = "open"
        task_escrow_balance = TASK_REWARD_AMOUNT
        bounty_available = BOUNTY_TOTAL_ESCROWED
        bounty_paid_out = 0
        attacker_reward_balance = 0
        successful_builds: list[dict] = []
        successful_deployments: list[dict] = []
        successful_delegations: list[dict] = []
        successful_executions: list[dict] = []

        for tx_model in tx_models:
            action = str(tx_model.instruction_type).upper()
            params = dict(tx_model.parameters_json or {})
            sequence_number = getattr(tx_model, "sequence_number", 0)
            if action == "BUILD_ATTACKER_PROGRAM":
                program_built = True
                successful_builds.append(
                    {
                        "transactionRef": tx_model.transaction_ref,
                        "sequenceNumber": sequence_number,
                        "programTemplate": params.get("program_template"),
                        "entrypointName": params.get("entrypoint_name"),
                        "artifactRef": params.get("artifact_ref", ATTACKER_PROGRAM_ARTIFACT_REF),
                    }
                )
            elif action == "DEPLOY_ATTACKER_PROGRAM":
                program_deployed = True
                successful_deployments.append(
                    {
                        "transactionRef": tx_model.transaction_ref,
                        "sequenceNumber": sequence_number,
                        "programRef": params.get("program_ref", ATTACKER_PROGRAM_REF),
                        "programAddress": params.get(
                            "program_address", str(self.attacker_program_address)
                        ),
                    }
                )
            elif action == "SUBMIT_DELEGATION":
                normal_delegation_submitted = True
                delegated_program = str(params.get("delegate_program_ref") or "official_payout_router")
                task_status = "delegated"
                successful_delegations.append(
                    {
                        "transactionRef": tx_model.transaction_ref,
                        "sequenceNumber": sequence_number,
                        "taskRef": params.get("task_ref"),
                        "delegateProgramRef": delegated_program,
                        "rewardAmount": int(params.get("executed_amount") or params.get("reward_amount") or 0),
                    }
                )
            elif action == "EXECUTE_DELEGATED_CPI":
                amount = int(params.get("executed_amount") or params.get("amount") or 0)
                if amount <= 0:
                    continue
                executed_target = str(params.get("delegate_program_ref") or ATTACKER_PROGRAM_REF)
                delegated_program = executed_target
                bounty_paid_out += amount
                bounty_available = max(bounty_available - amount, 0)
                attacker_reward_balance += amount
                task_escrow_balance = max(task_escrow_balance - amount, 0)
                task_status = "drained" if task_escrow_balance == 0 else "partially_drained"
                successful_executions.append(
                    {
                        "transactionRef": tx_model.transaction_ref,
                        "sequenceNumber": sequence_number,
                        "instructionName": params.get("instruction_name"),
                        "delegateProgramRef": executed_target,
                        "destinationAccountRef": params.get("destination_account_ref"),
                        "amount": amount,
                    }
                )

        bounty_pool = {
            "totalEscrowed": BOUNTY_TOTAL_ESCROWED,
            "availableLiquidity": bounty_available,
            "paidOut": bounty_paid_out,
        }
        task = {
            "taskId": "task-security-review-001",
            "status": task_status,
            "rewardAmount": TASK_REWARD_AMOUNT,
            "approvedDelegateProgram": "official_payout_router",
            "delegatedProgram": delegated_program,
            "escrowBalance": task_escrow_balance,
        }
        user = {
            "wallet": str(self.attacker_wallet),
            "normalDelegationSubmitted": normal_delegation_submitted,
        }
        attacker = {
            "programBuilt": program_built,
            "programDeployed": program_deployed,
            "programAddress": str(self.attacker_program_address) if program_deployed else None,
            "programRef": ATTACKER_PROGRAM_REF if program_deployed else None,
            "buildArtifactRef": ATTACKER_PROGRAM_ARTIFACT_REF if program_built else None,
            "drainDestination": "attacker_reward_account",
            "rewardBalance": attacker_reward_balance,
        }
        cpi = {
            "officialRouter": "official_payout_router",
            "executedTarget": executed_target,
            "targetReplaced": executed_target == ATTACKER_PROGRAM_REF,
        }
        return ArbitraryCPIState(
            bounty_pool=bounty_pool,
            task=task,
            user=user,
            attacker=attacker,
            cpi=cpi,
            successful_builds=successful_builds,
            successful_deployments=successful_deployments,
            successful_delegations=successful_delegations,
            successful_executions=successful_executions,
            failed_transactions=failed_transactions or [],
        )

    async def _failed_transactions(self) -> list[dict]:
        failed: list[dict] = []
        for tx_model in await self.all_transactions():
            if tx_model.execution_status == "success":
                continue
            failed.append(
                {
                    "transactionRef": tx_model.transaction_ref,
                    "sequenceNumber": tx_model.sequence_number,
                    "instructionType": tx_model.instruction_type,
                    "parameters": tx_model.parameters_json,
                }
            )
        return failed


class ArbitraryCPIRuntime:
    def __init__(self, template_root: Path, db_session: AsyncSession) -> None:
        self._template_root = template_root
        self._db_session = db_session

    async def read_file(self, path: str) -> str:
        template_path = (self._template_root / ARBITRARY_CPI_TEMPLATE_REF).resolve()
        file_path = (template_path / resolve_lab_file_path(path)).resolve()
        if template_path not in file_path.parents and file_path != template_path:
            raise ConflictError("Invalid file path")
        if file_path.exists() and file_path.is_file():
            return file_path.read_text(encoding="utf-8")
        return ""

    async def get_visible_accounts(self, session_id: str) -> list[SandboxAccountSummary]:
        mat = ArbitraryCPIMaterializer(self._template_root, self._db_session, session_id)
        state = await mat.state()
        pubkeys = mat.account_pubkeys(state)
        return [
            SandboxAccountSummary(
                ref=ref,
                label=RL3_ACCOUNT_LABELS[ref],
                owner=_owner_program(ref, str(mat.program_id)),
                lamports=0,
                data=_account_data(ref, state, mat),
            )
            for ref in _visible_refs(state)
            if ref in pubkeys
        ]

    async def get_account_state(self, session_id: str, account_ref: str) -> SandboxAccountSnapshot:
        mat = ArbitraryCPIMaterializer(self._template_root, self._db_session, session_id)
        state = await mat.state()
        pubkeys = mat.account_pubkeys(state)
        if account_ref not in pubkeys or account_ref not in _visible_refs(state):
            raise NotFoundError(f"Unknown account: {account_ref}")
        return SandboxAccountSnapshot(
            ref=account_ref,
            label=RL3_ACCOUNT_LABELS.get(account_ref, account_ref),
            owner=_owner_program(account_ref, str(mat.program_id)),
            lamports=0,
            data=_account_data(account_ref, state, mat),
        )

    async def get_explorer_snapshot(self, session_id: str) -> SandboxExplorerSnapshot:
        mat = ArbitraryCPIMaterializer(self._template_root, self._db_session, session_id)
        state = await mat.state()
        pubkeys = mat.account_pubkeys(state)
        program_address = str(mat.program_id)
        return SandboxExplorerSnapshot(
            session_id=session_id,
            network={"name": "SolBreach SVM", "kind": "sandbox"},
            program={
                "ref": "task_bounty",
                "address": program_address,
                "name": "task_bounty",
                "version": "1.0.0",
                "interfaceSource": "lab_idl",
                "idl": self._session_idl(program_address),
            },
            accounts=[
                _explorer_account(ref, pubkeys[ref], state, mat)
                for ref in _visible_refs(state)
                if ref in pubkeys
            ],
            protocol_state=_protocol_state(state),
        )

    async def submit_transaction(
        self, session_id: str, action_type: str, parameters: dict
    ) -> SandboxTransactionResult:
        mat = ArbitraryCPIMaterializer(self._template_root, self._db_session, session_id)
        before = await mat.state()
        action = action_type.upper()
        params = dict(parameters or {})

        if action == "BUILD_ATTACKER_PROGRAM":
            success, failure_code, logs, params = _execute_build(params)
        elif action == "DEPLOY_ATTACKER_PROGRAM":
            success, failure_code, logs, params = _execute_deploy(before, params, mat)
        elif action == "SUBMIT_DELEGATION":
            success, failure_code, logs, params = _execute_delegation(before, params)
        elif action == "EXECUTE_DELEGATED_CPI":
            success, failure_code, logs, params = _execute_cpi(before, params)
        else:
            success = False
            failure_code = "UNSUPPORTED_ACTION"
            logs = [f"Unsupported sandbox action: {action_type}"]

        extra_successful = []
        if success:
            parameters.clear()
            parameters.update(params)
            extra_successful.append(
                SimpleNamespace(
                    transaction_ref=f"tx_preview_{uuid4().hex[:8]}",
                    sequence_number=_success_count(before) + 1,
                    execution_status="success",
                    instruction_type=action,
                    parameters_json=params,
                )
            )
        after = await mat.state(extra_successful=extra_successful)
        protocol_state = _protocol_state(after)
        if failure_code is not None:
            protocol_state["lastRejectedReason"] = failure_code
        return SandboxTransactionResult(
            transaction_ref=f"tx_{uuid4().hex[:16]}",
            instruction_type=action,
            execution_status="success" if success else "failure",
            logs=logs,
            account_deltas=_build_deltas(before, after) if success else [],
            protocol_state=protocol_state,
            user_facing_evidence=[
                {
                    "type": "transaction_result" if success else "rejected_transaction",
                    "summary": "Transaction submitted." if success else _failure_summary(failure_code),
                    "errorCode": failure_code,
                }
            ],
        )

    async def verify_objective(
        self, session_id: str, objective_ref: str
    ) -> SandboxVerificationResult:
        if objective_ref != ARBITRARY_CPI_OBJECTIVE_REF:
            raise NotFoundError("Sandbox objective not found")
        mat = ArbitraryCPIMaterializer(self._template_root, self._db_session, session_id)
        state = await mat.state()
        tx_models = await mat.all_transactions()
        successful_build = _first_success(tx_models, "BUILD_ATTACKER_PROGRAM")
        successful_deploy = _first_success(tx_models, "DEPLOY_ATTACKER_PROGRAM")
        successful_delegation = _first_success(tx_models, "SUBMIT_DELEGATION")
        successful_cpi = next(
            (
                tx
                for tx in tx_models
                if tx.execution_status == "success"
                and tx.instruction_type == "EXECUTE_DELEGATED_CPI"
                and (tx.parameters_json or {}).get("instruction_name")
                == CANONICAL_EXECUTE_DELEGATED_PAYOUT
                and (tx.parameters_json or {}).get("delegate_program_ref") == ATTACKER_PROGRAM_REF
            ),
            None,
        )
        checks = {
            "attackerProgramBuilt": state.attacker["programBuilt"],
            "attackerProgramDeployed": state.attacker["programDeployed"],
            "normalDelegationSubmitted": state.user["normalDelegationSubmitted"],
            "canonicalInstructionUsed": successful_cpi is not None,
            "attackerProgramTargeted": state.cpi["executedTarget"] == ATTACKER_PROGRAM_REF,
            "officialRouterBypassed": state.cpi["targetReplaced"],
            "taskEscrowDrained": state.task["escrowBalance"] == 0,
            "attackerRewardIncreased": state.attacker["rewardBalance"] >= TASK_REWARD_AMOUNT,
            "bountyPoolPaidOut": state.bounty_pool["paidOut"] >= TASK_REWARD_AMOUNT,
        }
        passed = all(checks.values())
        missing_conditions = [key for key, value in checks.items() if not value]
        evidence_refs = []
        if successful_build is not None:
            evidence_refs.append(f"transaction:{successful_build.transaction_ref}")
        if successful_deploy is not None:
            evidence_refs.append(f"transaction:{successful_deploy.transaction_ref}")
        if successful_delegation is not None:
            evidence_refs.append(f"transaction:{successful_delegation.transaction_ref}")
        if successful_cpi is not None:
            evidence_refs.append(f"transaction:{successful_cpi.transaction_ref}")
        if checks["taskEscrowDrained"]:
            evidence_refs.append("account:task_escrow")
        if checks["attackerRewardIncreased"]:
            evidence_refs.append("account:attacker_reward_account")

        evidence = {
            "impact_verified": passed,
            "impactVerified": passed,
            "vulnerability_class": "ARBITRARY_CPI",
            "vulnerabilityClass": "ARBITRARY_CPI",
            "evidence_refs": evidence_refs,
            "evidenceRefs": evidence_refs,
            "missing_conditions": missing_conditions,
            "missingConditions": missing_conditions,
            "impactChecklist": checks,
            "protocolState": _protocol_state(state),
            "transactionTimeline": [
                {
                    "transactionRef": tx.transaction_ref,
                    "instructionType": tx.instruction_type,
                    "executionStatus": tx.execution_status,
                    "sequenceNumber": tx.sequence_number,
                    "evidenceRefs": tx.evidence_refs_json,
                }
                for tx in tx_models
            ],
            "accountDeltas": [
                delta for tx in tx_models for delta in (tx.account_deltas_json or [])
            ],
            "impact": {
                "drainedAmount": state.attacker["rewardBalance"],
                "bountyAvailableAfter": state.bounty_pool["availableLiquidity"],
                "executedCpiTarget": state.cpi["executedTarget"],
                "officialRouter": state.cpi["officialRouter"],
            },
        }
        failure_reason = (
            "Missing RL3 impact conditions: " + ", ".join(missing_conditions)
            if not passed
            else None
        )
        return SandboxVerificationResult(
            objective_ref=objective_ref,
            passed=passed,
            evidence=evidence,
            verified_evidence_refs=evidence_refs if passed else [],
            failure_reason=failure_reason,
            user_facing_evidence=(
                [
                    "Session-scoped attacker program was deployed before payout execution.",
                    "Delegated payout targeted the attacker CPI program and drained task escrow.",
                ]
                if passed
                else [failure_reason or "RL3 impact has not been verified."]
            ),
        )

    def _session_idl(self, program_address: str) -> dict:
        idl_path = self._template_root / ARBITRARY_CPI_TEMPLATE_REF / "idl" / "task_bounty.json"
        idl = json.loads(idl_path.read_text(encoding="utf-8"))
        idl["address"] = program_address
        idl.setdefault("metadata", {})["address"] = program_address
        return idl


def _visible_refs(state: ArbitraryCPIState) -> list[str]:
    refs = list(BASE_VISIBLE_REFS)
    if state.attacker["programDeployed"]:
        refs.append(ATTACKER_PROGRAM_REF)
    return refs


def _summary_data(ref: str, state: ArbitraryCPIState, mat: ArbitraryCPIMaterializer) -> dict:
    data = _account_data(ref, state, mat)
    if ref in {"bounty_vault", "task_escrow", "attacker_reward_account"}:
        return {"tokenAmount": data.get("amount", 0)}
    return data


def _explorer_account(
    ref: str, pubkey: Pubkey, state: ArbitraryCPIState, mat: ArbitraryCPIMaterializer
) -> dict:
    return {
        "ref": ref,
        "address": str(pubkey),
        "label": RL3_ACCOUNT_LABELS.get(ref, ref),
        "ownerProgram": _owner_program(ref, str(mat.program_id)),
        "accountType": _account_type(ref),
        "lamports": 0,
        "data": _account_data(ref, state, mat),
    }


def _owner_program(ref: str, program_address: str) -> str:
    if ref in {
        "bounty_config",
        "bounty_authority",
        "task_record",
        "official_payout_router",
        ATTACKER_PROGRAM_REF,
    }:
        return program_address
    if ref in {"approved_worker_account", "attacker_program_buffer"}:
        return SYSTEM_PROGRAM_ID
    return TOKEN_PROGRAM_ID


def _account_type(ref: str) -> str:
    return {
        "bounty_config": "BountyConfig",
        "bounty_authority": "ProgramDerivedAddress",
        "bounty_vault": "TokenAccount",
        "task_record": "TaskRecord",
        "task_escrow": "TokenAccount",
        "official_payout_router": "Program",
        "approved_worker_account": "TokenAccount",
        "attacker_reward_account": "TokenAccount",
        "attacker_program_buffer": "Buffer",
        ATTACKER_PROGRAM_REF: "Program",
    }.get(ref, "Account")


def _account_data(ref: str, state: ArbitraryCPIState, mat: ArbitraryCPIMaterializer) -> dict:
    if ref == "bounty_config":
        return {
            "authority": str(mat.bounty_authority),
            "bountyVault": str(mat.bounty_vault),
            "totalEscrowed": state.bounty_pool["totalEscrowed"],
            "availableLiquidity": state.bounty_pool["availableLiquidity"],
            "paidOut": state.bounty_pool["paidOut"],
        }
    if ref == "bounty_authority":
        return {"bountyConfig": str(mat.bounty_config)}
    if ref == "bounty_vault":
        return {"amount": state.bounty_pool["availableLiquidity"], "mintSymbol": "USDC"}
    if ref == "task_record":
        return state.task | {"address": str(mat.task_record)}
    if ref == "task_escrow":
        return {
            "amount": state.task["escrowBalance"],
            "taskRef": "task_record",
            "mintSymbol": "USDC",
        }
    if ref == "official_payout_router":
        return {
            "programRef": "official_payout_router",
            "approved": True,
            "description": "Canonical payout router configured by the TaskBounty protocol.",
        }
    if ref == "approved_worker_account":
        return {"amount": 0, "owner": "approved_worker"}
    if ref == "attacker_reward_account":
        return {"amount": state.attacker["rewardBalance"], "owner": state.user["wallet"]}
    if ref == "attacker_program_buffer":
        return {
            "artifactRef": ATTACKER_PROGRAM_ARTIFACT_REF
            if state.attacker["programBuilt"]
            else None,
            "built": state.attacker["programBuilt"],
            "deployed": state.attacker["programDeployed"],
        }
    if ref == ATTACKER_PROGRAM_REF:
        return {
            "programRef": ATTACKER_PROGRAM_REF,
            "programAddress": state.attacker["programAddress"],
            "template": ATTACKER_PROGRAM_TEMPLATE,
            "entrypoint": ATTACKER_ENTRYPOINT,
            "sessionScoped": True,
        }
    return {}


def _execute_build(params: dict) -> tuple[bool, str | None, list[str], dict]:
    if params.get("program_template") != ATTACKER_PROGRAM_TEMPLATE:
        return False, "INVALID_PROGRAM_TEMPLATE", ["Invalid attacker program template."], params
    if params.get("entrypoint_name") != ATTACKER_ENTRYPOINT:
        return False, "INVALID_ENTRYPOINT", ["Invalid attacker program entrypoint."], params
    if params.get("transfer_source_ref") != "task_escrow":
        return False, "INVALID_TRANSFER_SOURCE", ["Invalid transfer source account."], params
    if params.get("transfer_destination_ref") != "attacker_reward_account":
        return False, "INVALID_TRANSFER_DESTINATION", ["Invalid transfer destination account."], params
    if params.get("authority_strategy") != ATTACKER_AUTHORITY_STRATEGY:
        return False, "INVALID_AUTHORITY_STRATEGY", ["Invalid authority strategy."], params
    params["artifact_ref"] = ATTACKER_PROGRAM_ARTIFACT_REF
    return (
        True,
        None,
        [
            "Attacker program template selected.",
            "Deterministic session artifact built inside the SolBreach sandbox.",
        ],
        params,
    )


def _execute_deploy(
    state: ArbitraryCPIState, params: dict, mat: ArbitraryCPIMaterializer
) -> tuple[bool, str | None, list[str], dict]:
    if not state.attacker["programBuilt"]:
        return False, "ATTACKER_PROGRAM_NOT_BUILT", ["Build attacker program first."], params
    if state.attacker["programDeployed"]:
        return False, "ATTACKER_PROGRAM_ALREADY_DEPLOYED", ["Attacker program already deployed."], params
    if params.get("artifact_ref") != ATTACKER_PROGRAM_ARTIFACT_REF:
        return False, "INVALID_ARTIFACT_REF", ["Invalid attacker program artifact."], params
    params["program_ref"] = ATTACKER_PROGRAM_REF
    params["program_address"] = str(mat.attacker_program_address)
    return (
        True,
        None,
        [
            "Session-scoped attacker program registered in the SolBreach SVM.",
            "Deployment completed without moving task funds.",
        ],
        params,
    )


def _execute_delegation(
    state: ArbitraryCPIState, params: dict
) -> tuple[bool, str | None, list[str], dict]:
    if state.user["normalDelegationSubmitted"]:
        return False, "DELEGATION_ALREADY_SUBMITTED", ["Delegation already submitted."], params
    required_refs = {"task_ref": "task_record", "delegate_program_ref": "official_payout_router"}
    ref_error = _validate_refs(params, required_refs)
    if ref_error is not None:
        return False, ref_error, ["Invalid delegation account reference."], params
    amount = int(params.get("reward_amount") or 0)
    if amount != TASK_REWARD_AMOUNT:
        return False, "INVALID_REWARD_AMOUNT", ["Delegation amount must match the task reward."], params
    params["executed_amount"] = amount
    return (
        True,
        None,
        [
            "Task payout delegated to the official payout router.",
            "No funds moved during delegation submission.",
        ],
        params,
    )


def _execute_cpi(state: ArbitraryCPIState, params: dict) -> tuple[bool, str | None, list[str], dict]:
    instruction_name = params.get("instruction_name")
    if not instruction_name:
        return False, "INSTRUCTION_NAME_REQUIRED", ["Instruction name is required."], params
    if instruction_name != CANONICAL_EXECUTE_DELEGATED_PAYOUT:
        return (
            False,
            "INVALID_INSTRUCTION_NAME",
            ["Instruction name must match the public IDL instruction."],
            params,
        )
    if not state.user["normalDelegationSubmitted"]:
        return False, "DELEGATION_REQUIRED", ["Submit the normal delegation first."], params
    if not state.attacker["programDeployed"]:
        return False, "ATTACKER_PROGRAM_NOT_DEPLOYED", ["Deploy attacker program first."], params
    required_refs = {
        "task_ref": "task_record",
        "destination_account_ref": "attacker_reward_account",
    }
    ref_error = _validate_refs(params, required_refs)
    if ref_error is not None:
        return False, ref_error, ["Invalid CPI account reference."], params
    delegate_ref = params.get("delegate_program_ref")
    if delegate_ref == "official_payout_router":
        return (
            False,
            "OFFICIAL_ROUTER_TARGET_REJECTED",
            ["Official payout router target does not demonstrate arbitrary CPI replacement."],
            params,
        )
    if delegate_ref != ATTACKER_PROGRAM_REF:
        return False, "INVALID_CPI_TARGET", ["CPI target must be the deployed attacker program."], params
    amount = int(params.get("amount") or 0)
    if amount != TASK_REWARD_AMOUNT or amount > state.task["escrowBalance"]:
        return False, "INVALID_DRAIN_AMOUNT", ["Drain amount must match available task escrow."], params
    params["executed_amount"] = amount
    return (
        True,
        None,
        [
            "Vulnerable TaskBounty instruction accepted caller-supplied CPI target.",
            "Task escrow transferred through the session attacker program.",
        ],
        params,
    )


def _validate_refs(params: dict, expected: dict[str, str]) -> str | None:
    for key, expected_ref in expected.items():
        if params.get(key) != expected_ref:
            return "INVALID_ACCOUNT_REF"
    return None


def _failure_summary(code: str | None) -> str:
    return {
        "INVALID_PROGRAM_TEMPLATE": "Attacker program template is not supported.",
        "INVALID_ENTRYPOINT": "Attacker program entrypoint is not supported.",
        "INVALID_TRANSFER_SOURCE": "Transfer source must be the task escrow.",
        "INVALID_TRANSFER_DESTINATION": "Transfer destination must be the attacker reward account.",
        "INVALID_AUTHORITY_STRATEGY": "Authority strategy is not supported.",
        "ATTACKER_PROGRAM_NOT_BUILT": "Build attacker program before deployment.",
        "ATTACKER_PROGRAM_ALREADY_DEPLOYED": "Attacker program is already deployed.",
        "INVALID_ARTIFACT_REF": "Deployment artifact is invalid.",
        "DELEGATION_ALREADY_SUBMITTED": "Delegation has already been submitted.",
        "INVALID_ACCOUNT_REF": "One or more account refs do not belong to this action.",
        "INVALID_REWARD_AMOUNT": "Delegation reward amount must match the task reward.",
        "INSTRUCTION_NAME_REQUIRED": "Instruction name is required.",
        "INVALID_INSTRUCTION_NAME": "Instruction name does not match the public IDL.",
        "DELEGATION_REQUIRED": "Submit delegation before executing the CPI.",
        "ATTACKER_PROGRAM_NOT_DEPLOYED": "Deploy attacker program before executing the CPI.",
        "OFFICIAL_ROUTER_TARGET_REJECTED": "Official router target does not prove arbitrary CPI impact.",
        "INVALID_CPI_TARGET": "CPI target must be the deployed attacker program.",
        "INVALID_DRAIN_AMOUNT": "Drain amount must match available task escrow.",
        "UNSUPPORTED_ACTION": "Unsupported sandbox action.",
    }.get(code or "", "Transaction failed.")


def _build_deltas(before: ArbitraryCPIState, after: ArbitraryCPIState) -> list[dict]:
    pairs = [
        (
            "bounty_vault",
            "tokenAmount",
            before.bounty_pool["availableLiquidity"],
            after.bounty_pool["availableLiquidity"],
        ),
        (
            "bounty_config",
            "paidOut",
            before.bounty_pool["paidOut"],
            after.bounty_pool["paidOut"],
        ),
        (
            "task_escrow",
            "tokenAmount",
            before.task["escrowBalance"],
            after.task["escrowBalance"],
        ),
        (
            "attacker_reward_account",
            "tokenAmount",
            before.attacker["rewardBalance"],
            after.attacker["rewardBalance"],
        ),
    ]
    deltas = []
    for ref, field, old, new in pairs:
        if old == new:
            continue
        deltas.append(
            {
                "accountRef": ref,
                "label": RL3_ACCOUNT_LABELS.get(ref, ref),
                "field": field,
                "valueBefore": old,
                "valueAfter": new,
                "valueDelta": new - old,
            }
        )
    if before.task["status"] != after.task["status"]:
        deltas.append(
            {
                "accountRef": "task_record",
                "label": RL3_ACCOUNT_LABELS["task_record"],
                "field": "status",
                "valueBefore": before.task["status"],
                "valueAfter": after.task["status"],
            }
        )
    if before.attacker["programAddress"] != after.attacker["programAddress"]:
        deltas.append(
            {
                "accountRef": ATTACKER_PROGRAM_REF,
                "label": RL3_ACCOUNT_LABELS[ATTACKER_PROGRAM_REF],
                "field": "programAddress",
                "valueBefore": before.attacker["programAddress"],
                "valueAfter": after.attacker["programAddress"],
            }
        )
    return deltas


def _protocol_state(state: ArbitraryCPIState) -> dict:
    return {
        "bountyPool": state.bounty_pool,
        "task": state.task,
        "user": state.user,
        "attackerProgram": {
            "built": state.attacker["programBuilt"],
            "deployed": state.attacker["programDeployed"],
            "programAddress": state.attacker["programAddress"],
            "drainDestination": state.attacker["drainDestination"],
        },
        "attacker": state.attacker,
        "cpi": state.cpi,
        "successfulBuilds": state.successful_builds,
        "successfulDeployments": state.successful_deployments,
        "successfulDelegations": state.successful_delegations,
        "successfulExecutions": state.successful_executions,
        "failedTransactions": state.failed_transactions,
    }


def _success_count(state: ArbitraryCPIState) -> int:
    return (
        len(state.successful_builds)
        + len(state.successful_deployments)
        + len(state.successful_delegations)
        + len(state.successful_executions)
    )


def _first_success(
    transactions: list[ResearchLabTransactionModel], instruction_type: str
) -> ResearchLabTransactionModel | None:
    return next(
        (
            tx
            for tx in transactions
            if tx.execution_status == "success" and tx.instruction_type == instruction_type
        ),
        None,
    )
