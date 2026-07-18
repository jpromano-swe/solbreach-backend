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

YIELD_HIJACK_TEMPLATE_REF = "research-labs/yield-hijack@v1"
YIELD_HIJACK_OBJECTIVE_REF = "RL2_STATIC_PDA_REWARD_HIJACK_IMPACT"

VICTIM_STAKED_AMOUNT = 50_000
VICTIM_PENDING_REWARDS = 12_500
ATTACKER_INITIAL_STAKE = 100
ATTACKER_INITIAL_REWARD = 0
STAKE_VAULT_INITIAL_BALANCE = 50_000
REWARD_VAULT_INITIAL_BALANCE = 500_000
ADVERTISED_APY_BPS = 250_000
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"

YIELD_ACCOUNT_LABELS = {
    "pool_config": "Pool Configuration",
    "pool_authority": "Pool Authority",
    "stake_mint": "Stake Mint",
    "reward_mint": "Reward Mint",
    "stake_vault": "Stake Vault",
    "reward_vault": "Reward Vault",
    "stake_position": "Staking Position",
    "attacker_wallet": "Attacker Wallet",
    "victim_wallet": "Victim Wallet",
    "attacker_stake_account": "Attacker Stake Account",
    "attacker_reward_account": "Attacker Reward Account",
    "victim_stake_account": "Victim Stake Account",
    "victim_reward_account": "Victim Reward Account",
}


@dataclass(slots=True)
class YieldHijackState:
    pool: dict
    position: dict
    attacker: dict
    victim: dict
    derivations: dict
    successful_stakes: list[dict]
    successful_claims: list[dict]
    failed_transactions: list[dict]


class YieldHijackMaterializer:
    def __init__(self, template_root: Path, db_session: AsyncSession, session_id: str) -> None:
        self.template_root = template_root
        self.db_session = db_session
        self.session_id = session_id
        settings = get_settings()
        self._secret = (settings.jwt_secret_key or "dev_secret_key").encode()

        self.program_id = self._derive_keypair("program").pubkey()
        self.attacker = self._derive_keypair("attacker")
        self.victim = self._derive_keypair("victim")
        self.pool_config = self._derive_keypair("pool_config").pubkey()
        self.stake_mint = self._derive_keypair("stake_mint").pubkey()
        self.reward_mint = self._derive_keypair("reward_mint").pubkey()
        self.stake_vault = self._derive_keypair("stake_vault").pubkey()
        self.reward_vault = self._derive_keypair("reward_vault").pubkey()
        self.attacker_stake_account = self._derive_keypair("attacker_stake").pubkey()
        self.attacker_reward_account = self._derive_keypair("attacker_reward").pubkey()
        self.victim_stake_account = self._derive_keypair("victim_stake").pubkey()
        self.victim_reward_account = self._derive_keypair("victim_reward").pubkey()
        self.pool_authority, _ = Pubkey.find_program_address(
            [b"pool_authority", bytes(self.pool_config)], self.program_id
        )
        self.stake_position, _ = Pubkey.find_program_address(
            [b"stake_position", bytes(self.pool_config)], self.program_id
        )

    def account_pubkeys(self) -> dict[str, Pubkey]:
        return {
            "pool_config": self.pool_config,
            "pool_authority": self.pool_authority,
            "stake_mint": self.stake_mint,
            "reward_mint": self.reward_mint,
            "stake_vault": self.stake_vault,
            "reward_vault": self.reward_vault,
            "stake_position": self.stake_position,
            "attacker_wallet": self.attacker.pubkey(),
            "victim_wallet": self.victim.pubkey(),
            "attacker_stake_account": self.attacker_stake_account,
            "attacker_reward_account": self.attacker_reward_account,
            "victim_stake_account": self.victim_stake_account,
            "victim_reward_account": self.victim_reward_account,
        }

    def _derive_keypair(self, role: str) -> Keypair:
        msg = f"yield-hijack|v1|{self.session_id}|{role}".encode()
        return Keypair.from_seed(hmac.new(self._secret, msg, hashlib.sha256).digest()[:32])

    async def successful_transactions(self) -> list[ResearchLabTransactionModel]:
        if self.db_session is None:
            return []
        result = await self.db_session.execute(
            select(ResearchLabTransactionModel)
            .where(ResearchLabTransactionModel.session_id == self.session_id)
            .where(ResearchLabTransactionModel.execution_status == "success")
            .order_by(ResearchLabTransactionModel.sequence_number.asc())
        )
        return list(result.scalars().all())

    async def all_transactions(self) -> list[ResearchLabTransactionModel]:
        if self.db_session is None:
            return []
        result = await self.db_session.execute(
            select(ResearchLabTransactionModel)
            .where(ResearchLabTransactionModel.session_id == self.session_id)
            .order_by(ResearchLabTransactionModel.sequence_number.asc())
        )
        return list(result.scalars().all())

    async def state(
        self,
        extra_successful: list[ResearchLabTransactionModel | SimpleNamespace] | None = None,
    ) -> YieldHijackState:
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
    ) -> YieldHijackState:
        position_owner = str(self.victim.pubkey())
        staked_amount = VICTIM_STAKED_AMOUNT
        pending_rewards = VICTIM_PENDING_REWARDS
        attacker_stake_balance = ATTACKER_INITIAL_STAKE
        attacker_reward_balance = ATTACKER_INITIAL_REWARD
        stake_vault_balance = STAKE_VAULT_INITIAL_BALANCE
        reward_vault_balance = REWARD_VAULT_INITIAL_BALANCE
        successful_stakes: list[dict] = []
        successful_claims: list[dict] = []

        for tx_model in tx_models:
            action = str(tx_model.instruction_type).upper()
            params = dict(tx_model.parameters_json or {})
            if action == "STAKE":
                amount = int(params.get("executed_amount") or params.get("amount") or 0)
                if amount <= 0:
                    continue
                position_owner = str(self.attacker.pubkey())
                staked_amount += amount
                attacker_stake_balance = max(attacker_stake_balance - amount, 0)
                stake_vault_balance += amount
                successful_stakes.append(
                    {
                        "transactionRef": tx_model.transaction_ref,
                        "sequenceNumber": tx_model.sequence_number,
                        "amount": amount,
                    }
                )
            elif action == "CLAIM_REWARDS":
                amount = int(params.get("claimed_amount") or 0)
                if amount <= 0:
                    continue
                pending_rewards = max(pending_rewards - amount, 0)
                attacker_reward_balance += amount
                reward_vault_balance = max(reward_vault_balance - amount, 0)
                successful_claims.append(
                    {
                        "transactionRef": tx_model.transaction_ref,
                        "sequenceNumber": tx_model.sequence_number,
                        "amount": amount,
                    }
                )

        pool = {
            "address": str(self.pool_config),
            "authority": str(self.pool_authority),
            "stakeMint": str(self.stake_mint),
            "rewardMint": str(self.reward_mint),
            "advertisedApyBps": ADVERTISED_APY_BPS,
            "stakeVaultBalance": stake_vault_balance,
            "rewardVaultBalance": reward_vault_balance,
            "baselineRewardVaultBalance": REWARD_VAULT_INITIAL_BALANCE,
        }
        position = {
            "address": str(self.stake_position),
            "owner": position_owner,
            "baselineOwner": str(self.victim.pubkey()),
            "pool": str(self.pool_config),
            "stakedAmount": staked_amount,
            "baselineStakedAmount": VICTIM_STAKED_AMOUNT,
            "pendingRewards": pending_rewards,
            "baselinePendingRewards": VICTIM_PENDING_REWARDS,
        }
        attacker = {
            "wallet": str(self.attacker.pubkey()),
            "stakeBalance": attacker_stake_balance,
            "rewardBalance": attacker_reward_balance,
            "baselineStakeBalance": ATTACKER_INITIAL_STAKE,
            "baselineRewardBalance": ATTACKER_INITIAL_REWARD,
        }
        victim = {
            "wallet": str(self.victim.pubkey()),
            "stakeBalance": 0,
            "rewardBalance": 0,
            "baselineStakedAmount": VICTIM_STAKED_AMOUNT,
            "baselinePendingRewards": VICTIM_PENDING_REWARDS,
        }
        derivations = {
            "victim_position": {
                "address": str(self.stake_position),
                "seeds": ["stake_position", str(self.pool_config)],
            },
            "attacker_position": {
                "address": str(self.stake_position),
                "seeds": ["stake_position", str(self.pool_config)],
            },
        }
        return YieldHijackState(
            pool=pool,
            position=position,
            attacker=attacker,
            victim=victim,
            derivations=derivations,
            successful_stakes=successful_stakes,
            successful_claims=successful_claims,
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


class YieldHijackRuntime:
    def __init__(self, template_root: Path, db_session: AsyncSession) -> None:
        self._template_root = template_root
        self._db_session = db_session

    async def read_file(self, path: str) -> str:
        template_path = (self._template_root / YIELD_HIJACK_TEMPLATE_REF).resolve()
        file_path = (template_path / resolve_lab_file_path(path)).resolve()
        if template_path not in file_path.parents and file_path != template_path:
            raise ConflictError("Invalid file path")
        if file_path.exists() and file_path.is_file():
            return file_path.read_text(encoding="utf-8")
        return ""

    async def get_visible_accounts(self, session_id: str) -> list[SandboxAccountSummary]:
        mat = YieldHijackMaterializer(self._template_root, self._db_session, session_id)
        state = await mat.state()
        pubkeys = mat.account_pubkeys()
        return [
            _summary(
                "pool_config", pubkeys["pool_config"], {"advertisedApyBps": ADVERTISED_APY_BPS}
            ),
            _summary("pool_authority", pubkeys["pool_authority"], {"pool": str(mat.pool_config)}),
            _summary("stake_mint", pubkeys["stake_mint"], {"symbol": "STAKE"}),
            _summary("reward_mint", pubkeys["reward_mint"], {"symbol": "REWARD"}),
            _summary(
                "stake_vault",
                pubkeys["stake_vault"],
                {"tokenAmount": state.pool["stakeVaultBalance"], "mint": str(mat.stake_mint)},
            ),
            _summary(
                "reward_vault",
                pubkeys["reward_vault"],
                {"tokenAmount": state.pool["rewardVaultBalance"], "mint": str(mat.reward_mint)},
            ),
            _summary("stake_position", pubkeys["stake_position"], state.position),
            _summary(
                "attacker_stake_account",
                pubkeys["attacker_stake_account"],
                {
                    "tokenAmount": state.attacker["stakeBalance"],
                    "owner": str(mat.attacker.pubkey()),
                },
            ),
            _summary(
                "attacker_reward_account",
                pubkeys["attacker_reward_account"],
                {
                    "tokenAmount": state.attacker["rewardBalance"],
                    "owner": str(mat.attacker.pubkey()),
                },
            ),
            _summary(
                "victim_stake_account",
                pubkeys["victim_stake_account"],
                {"tokenAmount": state.victim["stakeBalance"], "owner": str(mat.victim.pubkey())},
            ),
            _summary(
                "victim_reward_account",
                pubkeys["victim_reward_account"],
                {"tokenAmount": state.victim["rewardBalance"], "owner": str(mat.victim.pubkey())},
            ),
        ]

    async def get_account_state(self, session_id: str, account_ref: str) -> SandboxAccountSnapshot:
        mat = YieldHijackMaterializer(self._template_root, self._db_session, session_id)
        state = await mat.state()
        pubkeys = mat.account_pubkeys()
        if account_ref not in pubkeys:
            raise NotFoundError(f"Unknown account: {account_ref}")
        data = _account_data(account_ref, state, mat)
        return SandboxAccountSnapshot(
            ref=account_ref,
            label=YIELD_ACCOUNT_LABELS.get(account_ref, account_ref),
            owner=str(mat.program_id),
            lamports=0,
            data=data,
        )

    async def get_explorer_snapshot(self, session_id: str) -> SandboxExplorerSnapshot:
        mat = YieldHijackMaterializer(self._template_root, self._db_session, session_id)
        state = await mat.state()
        pubkeys = mat.account_pubkeys()
        program_address = str(mat.program_id)
        idl = self._session_idl(program_address)
        return SandboxExplorerSnapshot(
            session_id=session_id,
            network={"name": "SolBreach SVM", "kind": "sandbox"},
            program={
                "ref": "yield_hijack",
                "address": program_address,
                "name": "yield_hijack",
                "version": "1.0.0",
                "interfaceSource": "lab_idl",
                "idl": idl,
            },
            accounts=[
                _explorer_account(ref, pubkeys[ref], state, mat)
                for ref in [
                    "pool_config",
                    "pool_authority",
                    "stake_mint",
                    "reward_mint",
                    "stake_vault",
                    "reward_vault",
                    "stake_position",
                    "attacker_stake_account",
                    "attacker_reward_account",
                    "victim_stake_account",
                    "victim_reward_account",
                ]
            ],
            reward_candidates=_reward_candidates(state),
            total_rewards_paid=sum(item["amount"] for item in state.successful_claims),
        )

    async def submit_transaction(
        self, session_id: str, action_type: str, parameters: dict
    ) -> SandboxTransactionResult:
        mat = YieldHijackMaterializer(self._template_root, self._db_session, session_id)
        before = await mat.state()
        action = action_type.upper()
        params = dict(parameters or {})
        success = False
        logs: list[str] = []
        failure_code: str | None = None

        if action == "STAKE":
            success, failure_code, logs, params = _execute_stake(before, params)
        elif action == "CLAIM_REWARDS":
            success, failure_code, logs, params = _execute_claim(before, params)
        else:
            failure_code = "UNSUPPORTED_ACTION"
            logs = [f"Unsupported sandbox action: {action_type}"]

        extra_successful = []
        if success:
            parameters.clear()
            parameters.update(params)
            extra_successful.append(
                SimpleNamespace(
                    transaction_ref=f"tx_preview_{uuid4().hex[:8]}",
                    sequence_number=len(before.successful_stakes)
                    + len(before.successful_claims)
                    + 1,
                    execution_status="success",
                    instruction_type=action,
                    parameters_json=params,
                )
            )
        after = await mat.state(extra_successful=extra_successful)
        account_deltas = _build_yield_deltas(before, after)
        protocol_state = _protocol_state(after)
        if failure_code is not None:
            protocol_state["lastRejectedReason"] = failure_code
        return SandboxTransactionResult(
            transaction_ref=f"tx_{uuid4().hex[:16]}",
            instruction_type=action,
            execution_status="success" if success else "failure",
            logs=logs,
            account_deltas=account_deltas if success else [],
            protocol_state=protocol_state,
            user_facing_evidence=[
                {
                    "type": "transaction_result" if success else "rejected_transaction",
                    "summary": "Transaction submitted."
                    if success
                    else _failure_summary(failure_code),
                    "errorCode": failure_code,
                }
            ],
        )

    async def verify_objective(
        self, session_id: str, objective_ref: str
    ) -> SandboxVerificationResult:
        mat = YieldHijackMaterializer(self._template_root, self._db_session, session_id)
        state = await mat.state()
        tx_models = await mat.all_transactions()
        successful_stake = next(
            (
                tx
                for tx in tx_models
                if tx.execution_status == "success" and tx.instruction_type == "STAKE"
            ),
            None,
        )
        successful_claim = next(
            (
                tx
                for tx in tx_models
                if tx.execution_status == "success" and tx.instruction_type == "CLAIM_REWARDS"
            ),
            None,
        )
        attacker_staked = sum(item["amount"] for item in state.successful_stakes)
        rewards_claimed = sum(item["amount"] for item in state.successful_claims)
        attacker_reward_delta = state.attacker["rewardBalance"] - ATTACKER_INITIAL_REWARD
        reward_vault_delta = state.pool["rewardVaultBalance"] - REWARD_VAULT_INITIAL_BALANCE
        derivation_collision = (
            state.derivations["victim_position"]["address"]
            == state.derivations["attacker_position"]["address"]
        )
        checks = {
            "baselinePositionOwnerWasVictim": state.position["baselineOwner"]
            == str(mat.victim.pubkey()),
            "currentPositionOwnerIsAttacker": state.position["owner"] == str(mat.attacker.pubkey()),
            "attackerStakeObserved": successful_stake is not None,
            "victimStakePreserved": state.position["stakedAmount"]
            == VICTIM_STAKED_AMOUNT + attacker_staked,
            "rewardClaimObserved": successful_claim is not None,
            "attackerRewardsIncreased": attacker_reward_delta > 0,
            "rewardVaultDecreased": reward_vault_delta < 0,
            "rewardDeltaMatches": attacker_reward_delta == -reward_vault_delta,
            "claimedPreExistingRewards": rewards_claimed == VICTIM_PENDING_REWARDS,
            "pendingRewardsZero": state.position["pendingRewards"] == 0,
            "positionDerivationCollision": derivation_collision,
        }
        passed = all(checks.values())
        missing_conditions = [key for key, value in checks.items() if not value]
        evidence_refs = []
        if derivation_collision:
            evidence_refs.append("position_address_collision")
        if checks["currentPositionOwnerIsAttacker"]:
            evidence_refs.append("position_owner_overwritten")
        if checks["victimStakePreserved"]:
            evidence_refs.append("victim_value_preserved")
        if checks["attackerRewardsIncreased"]:
            evidence_refs.append("attacker_rewards_increased")
        if checks["rewardVaultDecreased"]:
            evidence_refs.append("reward_vault_decreased")

        evidence = {
            "impact_verified": passed,
            "impactVerified": passed,
            "vulnerability_class": "STATIC_PDA",
            "vulnerabilityClass": "STATIC_PDA",
            "evidence_refs": evidence_refs,
            "evidenceRefs": evidence_refs,
            "missing_conditions": missing_conditions,
            "missingConditions": missing_conditions,
            "impact": {
                "attacker_staked": attacker_staked,
                "attackerStaked": attacker_staked,
                "rewards_claimed": rewards_claimed,
                "rewardsClaimed": rewards_claimed,
                "position_owner_before": state.position["baselineOwner"],
                "positionOwnerBefore": state.position["baselineOwner"],
                "position_owner_after": state.position["owner"],
                "positionOwnerAfter": state.position["owner"],
            },
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
        }
        if not passed:
            failure_reason = "Missing RL2 impact conditions: " + ", ".join(missing_conditions)
        else:
            failure_reason = None
        return SandboxVerificationResult(
            objective_ref=objective_ref,
            passed=passed,
            evidence=evidence,
            verified_evidence_refs=evidence_refs,
            failure_reason=failure_reason,
            user_facing_evidence=(
                [
                    "Shared staking-position PDA was overwritten by the attacker.",
                    "Pre-existing victim rewards were claimed by the attacker.",
                ]
                if passed
                else [failure_reason or "RL2 impact has not been verified."]
            ),
        )

    def _session_idl(self, program_address: str) -> dict:
        idl_path = self._template_root / YIELD_HIJACK_TEMPLATE_REF / "idl" / "yield_hijack.json"
        idl = json.loads(idl_path.read_text(encoding="utf-8"))
        idl["address"] = program_address
        idl.setdefault("metadata", {})["address"] = program_address
        return idl


def _summary(ref: str, pubkey: Pubkey, data: dict) -> SandboxAccountSummary:
    return SandboxAccountSummary(
        ref=ref,
        label=YIELD_ACCOUNT_LABELS.get(ref, ref),
        owner=str(pubkey),
        lamports=0,
        data=data,
    )


def _explorer_account(
    ref: str, pubkey: Pubkey, state: YieldHijackState, mat: YieldHijackMaterializer
) -> dict:
    program_address = str(mat.program_id)
    return {
        "ref": ref,
        "address": str(pubkey),
        "label": YIELD_ACCOUNT_LABELS.get(ref, ref),
        "ownerProgram": _owner_program(ref, program_address),
        "accountType": _account_type(ref),
        "lamports": 0,
        "data": _account_data(ref, state, mat),
    }


def _owner_program(ref: str, program_address: str) -> str:
    if ref in {"pool_config", "pool_authority", "stake_position"}:
        return program_address
    return TOKEN_PROGRAM_ID


def _account_type(ref: str) -> str:
    return {
        "pool_config": "PoolConfig",
        "pool_authority": "ProgramDerivedAddress",
        "stake_mint": "Mint",
        "reward_mint": "Mint",
        "stake_vault": "TokenAccount",
        "reward_vault": "TokenAccount",
        "stake_position": "StakePosition",
        "attacker_stake_account": "TokenAccount",
        "attacker_reward_account": "TokenAccount",
        "victim_stake_account": "TokenAccount",
        "victim_reward_account": "TokenAccount",
    }.get(ref, "Account")


def _reward_candidates(state: YieldHijackState) -> list[dict]:
    pending_rewards = int(state.position["pendingRewards"])
    if pending_rewards <= 0:
        return []
    return [
        {
            "walletAddress": state.position["baselineOwner"],
            "positionAddress": state.position["address"],
            "pendingRewards": pending_rewards,
        }
    ]


def _account_data(ref: str, state: YieldHijackState, mat: YieldHijackMaterializer) -> dict:
    if ref == "pool_config":
        return state.pool
    if ref == "pool_authority":
        return {"pool": str(mat.pool_config)}
    if ref == "stake_position":
        return state.position | {"derivations": state.derivations}
    if ref == "stake_vault":
        return {"amount": state.pool["stakeVaultBalance"], "mint": str(mat.stake_mint)}
    if ref == "reward_vault":
        return {"amount": state.pool["rewardVaultBalance"], "mint": str(mat.reward_mint)}
    if ref == "attacker_stake_account":
        return {"amount": state.attacker["stakeBalance"], "owner": str(mat.attacker.pubkey())}
    if ref == "attacker_reward_account":
        return {"amount": state.attacker["rewardBalance"], "owner": str(mat.attacker.pubkey())}
    if ref == "victim_stake_account":
        return {"amount": state.victim["stakeBalance"], "owner": str(mat.victim.pubkey())}
    if ref == "victim_reward_account":
        return {"amount": state.victim["rewardBalance"], "owner": str(mat.victim.pubkey())}
    if ref == "stake_mint":
        return {"symbol": "STAKE"}
    if ref == "reward_mint":
        return {"symbol": "REWARD"}
    return {}


def _execute_stake(
    state: YieldHijackState, params: dict
) -> tuple[bool, str | None, list[str], dict]:
    amount = int(params.get("amount") or 0)
    if amount <= 0:
        return False, "INVALID_AMOUNT", ["Stake amount must be positive."], params
    if amount > state.attacker["stakeBalance"]:
        return (
            False,
            "INSUFFICIENT_STAKE_BALANCE",
            ["Stake amount exceeds attacker balance."],
            params,
        )
    required_refs = {
        "source_account_ref": "attacker_stake_account",
        "stake_vault_ref": "stake_vault",
        "position_account_ref": "stake_position",
    }
    ref_error = _validate_refs(params, required_refs)
    if ref_error is not None:
        return False, ref_error, ["Invalid session account reference."], params
    params["executed_amount"] = amount
    return (
        True,
        None,
        [
            "Stake transferred into the pool vault.",
            "Shared staking position owner overwritten by signer.",
        ],
        params,
    )


def _execute_claim(
    state: YieldHijackState, params: dict
) -> tuple[bool, str | None, list[str], dict]:
    required_refs = {
        "position_account_ref": "stake_position",
        "reward_vault_ref": "reward_vault",
        "destination_account_ref": "attacker_reward_account",
    }
    ref_error = _validate_refs(params, required_refs)
    if ref_error is not None:
        return False, ref_error, ["Invalid session account reference."], params
    target_wallet = params.get("target_wallet_address")
    if not target_wallet:
        return False, "TARGET_WALLET_REQUIRED", ["Target wallet address is required."], params
    if target_wallet != state.position["baselineOwner"]:
        return (
            False,
            "INVALID_TARGET_WALLET",
            ["Target wallet does not match reward candidate."],
            params,
        )
    if state.position["owner"] != state.attacker["wallet"]:
        return (
            False,
            "INVALID_POSITION_OWNER",
            ["Claim rejected: signer does not own position."],
            params,
        )
    amount = int(state.position["pendingRewards"])
    if amount <= 0:
        return False, "NO_REWARDS_AVAILABLE", ["Claim rejected: no rewards available."], params
    params["claimed_amount"] = amount
    return True, None, ["Pending rewards claimed by current position owner."], params


def _validate_refs(params: dict, expected: dict[str, str]) -> str | None:
    for key, expected_ref in expected.items():
        actual = params.get(key)
        if actual != expected_ref:
            return "INVALID_ACCOUNT_REF"
    return None


def _failure_summary(code: str | None) -> str:
    return {
        "INVALID_AMOUNT": "Stake amount must be greater than zero.",
        "INSUFFICIENT_STAKE_BALANCE": "Stake amount exceeds the attacker stake balance.",
        "INVALID_ACCOUNT_REF": "One or more account refs do not belong to this session action.",
        "TARGET_WALLET_REQUIRED": "Target wallet address is required.",
        "INVALID_TARGET_WALLET": "Target wallet does not match the reward candidate.",
        "INVALID_POSITION_OWNER": "The attacker does not own the staking position yet.",
        "NO_REWARDS_AVAILABLE": "No rewards are available to claim.",
        "UNSUPPORTED_ACTION": "Unsupported sandbox action.",
    }.get(code or "", "Transaction failed.")


def _build_yield_deltas(before: YieldHijackState, after: YieldHijackState) -> list[dict]:
    pairs = [
        (
            "stake_position",
            "stakedAmount",
            before.position["stakedAmount"],
            after.position["stakedAmount"],
        ),
        (
            "stake_position",
            "pendingRewards",
            before.position["pendingRewards"],
            after.position["pendingRewards"],
        ),
        (
            "stake_vault",
            "tokenAmount",
            before.pool["stakeVaultBalance"],
            after.pool["stakeVaultBalance"],
        ),
        (
            "reward_vault",
            "tokenAmount",
            before.pool["rewardVaultBalance"],
            after.pool["rewardVaultBalance"],
        ),
        (
            "attacker_stake_account",
            "tokenAmount",
            before.attacker["stakeBalance"],
            after.attacker["stakeBalance"],
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
                "label": YIELD_ACCOUNT_LABELS.get(ref, ref),
                "field": field,
                "valueBefore": old,
                "valueAfter": new,
                "valueDelta": new - old,
            }
        )
    if before.position["owner"] != after.position["owner"]:
        deltas.append(
            {
                "accountRef": "stake_position",
                "label": YIELD_ACCOUNT_LABELS["stake_position"],
                "field": "owner",
                "valueBefore": before.position["owner"],
                "valueAfter": after.position["owner"],
            }
        )
    return deltas


def _protocol_state(state: YieldHijackState) -> dict:
    return {
        "pool": state.pool,
        "position": state.position,
        "attacker": state.attacker,
        "victim": state.victim,
        "derivations": state.derivations,
        "successfulStakes": state.successful_stakes,
        "successfulClaims": state.successful_claims,
        "failedTransactions": state.failed_transactions,
        "attackerStakedTotal": sum(item["amount"] for item in state.successful_stakes),
        "rewardsClaimedTotal": sum(item["amount"] for item in state.successful_claims),
        "positionDerivationCollision": (
            state.derivations["victim_position"]["address"]
            == state.derivations["attacker_position"]["address"]
        ),
    }
