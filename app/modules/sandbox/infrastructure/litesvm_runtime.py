import time
import hmac
import hashlib
from types import SimpleNamespace
from uuid import uuid4
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from solders.litesvm import LiteSVM
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.instruction import Instruction, AccountMeta
from solders.message import Message
from solders.transaction import VersionedTransaction
from solders.account import Account
from solders.transaction_metadata import FailedTransactionMetadata

from app.core.config.settings import get_settings
from app.core.exceptions.domain import NotFoundError
from app.modules.sandbox.domain.runtime import (
    SandboxAccountSnapshot,
    SandboxAccountSummary,
    resolve_lab_file_path,
    resolve_lab_template_ref,
    SandboxRuntime,
    SandboxTerminalEvent,
    SandboxTestResult,
    SandboxTestRunResult,
    SandboxTransactionResult,
    SandboxVerificationResult,
)
from app.modules.labs.infrastructure.database.models import ResearchLabTransactionModel

TOKEN_PROGRAM_ID = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
SYS_PROGRAM_ID = Pubkey.from_string("11111111111111111111111111111111")
PROGRAM_ID = Pubkey.from_string("Mirage1111111111111111111111111111111111111")
INITIAL_TREASURY_LAMPORTS = 5_000_000_000
INITIAL_REWARD_LAMPORTS = 1_000_000_000
OFFICIAL_COLLATERAL_START = 50_000
COUNTERFEIT_COLLATERAL_START = 500_000
LTV_BPS = 8_000

LAB_ACCOUNT_MAP = {
    "treasury_vault": {"label": "Protocol Treasury", "pda": True},
    "position": {"label": "Borrow Position", "pda": True},
    "attacker_reward_account": {"label": "Learner Reward Wallet", "pda": False, "key_role": "attacker"},
    "attacker_wallet": {"label": "Learner Reward Wallet", "pda": False, "key_role": "attacker"},
    "payer_wallet": {"label": "Payer Wallet", "pda": False, "key_role": "payer"},
    "counterfeit_mint_account": {"label": "Candidate Collateral Mint", "pda": False, "key_role": "cmint"},
    "official_mint_account": {"label": "Approved Collateral Mint", "pda": False, "key_role": "omint"},
    "attacker_collateral_account": {"label": "Candidate Collateral Account", "pda": False, "key_role": "acollat"},
    "official_collateral_account": {"label": "Official Collateral Account", "pda": False, "key_role": "ocollat"},
    "counterfeit_vault_account": {"label": "External Vault", "pda": False, "key_role": "cvault"},
    "official_vault_account": {"label": "Official Vault", "pda": False, "key_role": "ovault"},
}


def _discriminator(namespace: str, name: str) -> bytes:
    return hashlib.sha256(f"{namespace}:{name}".encode()).digest()[:8]


def _spl_token_data(mint: Pubkey, owner: Pubkey, amount: int) -> bytes:
    data = bytearray(165)
    data[0:32] = bytes(mint)
    data[32:64] = bytes(owner)
    data[64:72] = amount.to_bytes(8, "little")
    data[108] = 1
    return bytes(data)


def _position_credit(data: bytes | bytearray) -> int:
    if len(data) < 48:
        return 0
    return int.from_bytes(data[40:48], "little")


def _set_position_credit(svm: LiteSVM, position_pda: Pubkey, credited_collateral: int) -> None:
    account = svm.get_account(position_pda)
    if account is None:
        return
    raw = bytearray(account.data)
    if len(raw) < 48:
        return
    raw[40:48] = int(credited_collateral).to_bytes(8, "little")
    svm.set_account(
        position_pda,
        Account(
            lamports=account.lamports,
            data=bytes(raw),
            owner=account.owner,
            executable=account.executable,
            rent_epoch=account.rent_epoch,
        ),
    )


def _token_amount(data: bytes | bytearray) -> int:
    if len(data) < 72:
        return 0
    return int.from_bytes(data[64:72], "little")


def _borrow_quote(credited_collateral: int, treasury_lamports: int, borrowed_total: int) -> dict[str, int | bool]:
    gross_max_borrow = (credited_collateral * LTV_BPS) // 10_000
    remaining_credit = max(gross_max_borrow - borrowed_total, 0)
    max_borrow = min(remaining_credit, treasury_lamports)
    return {
        "ltvBps": LTV_BPS,
        "grossMaxBorrow": gross_max_borrow,
        "borrowedTotal": borrowed_total,
        "availableBorrow": max_borrow,
        "borrowAllowed": max_borrow > 0,
    }


def _deposit_path_type(collateral_ref: str | None, vault_ref: str | None) -> str:
    if collateral_ref in {
        "official_collateral",
        "official_collateral_account",
    } and vault_ref in {
        "official_vault",
        "official_vault_account",
    }:
        return "official"
    if collateral_ref in {
        "attacker_collateral",
        "attacker_collateral_account",
        "candidate_collateral",
        "candidate_collateral_account",
    } and vault_ref in {
        "counterfeit_vault",
        "counterfeit_vault_account",
        "external_vault",
        "external_vault_account",
    }:
        return "exploit"
    return "mixed"


def _derive_protocol_state(
    tx_models: list[ResearchLabTransactionModel],
    credited_collateral: int,
    treasury_lamports: int,
    reward_lamports: int,
) -> dict:
    successful_deposits: list[dict] = []
    successful_withdrawals: list[dict] = []
    for tx_model in tx_models:
        if tx_model.execution_status != "success":
            continue
        if tx_model.instruction_type == "DEPOSIT_COLLATERAL":
            params = tx_model.parameters_json or {}
            successful_deposits.append(
                {
                    "transactionRef": tx_model.transaction_ref,
                    "sequenceNumber": tx_model.sequence_number,
                    "pathType": _deposit_path_type(
                        params.get("collateral_account_ref"),
                        params.get("vault_account_ref"),
                    ),
                }
            )
        elif tx_model.instruction_type == "WITHDRAW_AGAINST_CREDIT":
            successful_withdrawals.append(
                {
                    "transactionRef": tx_model.transaction_ref,
                    "sequenceNumber": tx_model.sequence_number,
                    "amount": int((tx_model.parameters_json or {}).get("amount") or 0),
                }
            )

    deposit_path_type = "none"
    deposit_types = {item["pathType"] for item in successful_deposits}
    if deposit_types == {"official"}:
        deposit_path_type = "official"
    elif deposit_types == {"exploit"}:
        deposit_path_type = "exploit"
    elif deposit_types:
        deposit_path_type = "mixed"

    borrowed_total = max(reward_lamports - INITIAL_REWARD_LAMPORTS, 0)
    if successful_withdrawals:
        borrowed_total = sum(item["amount"] for item in successful_withdrawals)
    quoted_collateral = credited_collateral + borrowed_total
    quoted_treasury = treasury_lamports + borrowed_total
    borrow_quote = _borrow_quote(quoted_collateral, quoted_treasury, borrowed_total)

    return {
        "depositPathType": deposit_path_type,
        "creditedCollateral": credited_collateral,
        "quotedCollateral": quoted_collateral,
        "treasuryLamports": treasury_lamports,
        "initialTreasuryLamports": INITIAL_TREASURY_LAMPORTS,
        "rewardLamports": reward_lamports,
        "successfulDeposits": successful_deposits,
        "successfulWithdrawals": successful_withdrawals,
        "maxBorrow": borrow_quote["grossMaxBorrow"],
        "availableBorrow": borrow_quote["availableBorrow"],
        "borrowedTotal": borrow_quote["borrowedTotal"],
        "borrowAllowed": borrow_quote["borrowAllowed"],
        "ltvBps": borrow_quote["ltvBps"],
        "maxDrainSatisfied": borrow_quote["availableBorrow"] == 0 and borrowed_total > 0,
    }


def _snapshot_accounts(svm: LiteSVM, mat: "SessionMaterializer", refs: list[str]) -> dict[str, dict]:
    snapshots: dict[str, dict] = {}
    for ref in refs:
        pk = mat.account_pubkeys().get(ref)
        if pk is None:
            continue
        account = svm.get_account(pk)
        if account is None:
            snapshots[ref] = {"exists": False}
            continue
        payload = {
            "exists": True,
            "owner": str(account.owner),
            "lamports": account.lamports,
            "data": {},
        }
        if ref == "position":
            payload["data"]["credit"] = _position_credit(account.data)
        elif str(account.owner) == str(TOKEN_PROGRAM_ID) and len(account.data) >= 165:
            payload["data"]["mint"] = str(Pubkey.from_bytes(account.data[0:32]))
            payload["data"]["token_owner"] = str(Pubkey.from_bytes(account.data[32:64]))
            payload["data"]["amount"] = int.from_bytes(account.data[64:72], "little")
        snapshots[ref] = payload
    return snapshots


def _build_account_deltas(before: dict[str, dict], after: dict[str, dict]) -> list[dict]:
    deltas: list[dict] = []
    for ref in sorted(set(before) | set(after)):
        previous = before.get(ref, {"exists": False})
        current = after.get(ref, {"exists": False})
        before_lamports = int(previous.get("lamports", 0) or 0)
        after_lamports = int(current.get("lamports", 0) or 0)
        before_amount = int(previous.get("data", {}).get("amount", previous.get("data", {}).get("credit", 0)) or 0)
        after_amount = int(current.get("data", {}).get("amount", current.get("data", {}).get("credit", 0)) or 0)
        if (
            previous.get("exists") != current.get("exists")
            or before_lamports != after_lamports
            or before_amount != after_amount
        ):
            deltas.append(
                {
                    "accountRef": ref,
                    "label": LAB_ACCOUNT_MAP.get(ref, {}).get("label", ref),
                    "lamportsBefore": before_lamports,
                    "lamportsAfter": after_lamports,
                    "lamportsDelta": after_lamports - before_lamports,
                    "valueBefore": before_amount,
                    "valueAfter": after_amount,
                    "valueDelta": after_amount - before_amount,
                }
            )
    return deltas


class SessionMaterializer:
    def __init__(self, template_root: Path, db_session: AsyncSession, session_id: str):
        self.template_root = template_root
        self.db_session = db_session
        self.session_id = session_id
        self.metrics: dict[str, float] = {}

        settings = get_settings()
        self._secret = (settings.jwt_secret_key or "dev_secret_key").encode()

        self.payer = self._derive_keypair("payer")
        self.attacker = self._derive_keypair("attacker")
        self.counterfeit_mint = self._derive_keypair("cmint").pubkey()
        self.official_mint = self._derive_keypair("omint").pubkey()
        self.counterfeit_vault_pk = self._derive_keypair("cvault").pubkey()
        self.official_vault_pk = self._derive_keypair("ovault").pubkey()
        self.attacker_collateral_pk = self._derive_keypair("acollat").pubkey()
        self.official_collateral_pk = self._derive_keypair("ocollat").pubkey()

        self.treasury_pda, _ = Pubkey.find_program_address([b"treasury"], PROGRAM_ID)
        self.position_pda, _ = Pubkey.find_program_address(
            [b"position", bytes(self.attacker.pubkey())], PROGRAM_ID
        )

    def account_pubkeys(self) -> dict[str, Pubkey]:
        return {
            "treasury_vault": self.treasury_pda,
            "position": self.position_pda,
            "attacker_reward_account": self.attacker.pubkey(),
            "attacker_wallet": self.attacker.pubkey(),
            "payer_wallet": self.payer.pubkey(),
            "counterfeit_mint_account": self.counterfeit_mint,
            "official_mint_account": self.official_mint,
            "attacker_collateral_account": self.attacker_collateral_pk,
            "official_collateral_account": self.official_collateral_pk,
            "counterfeit_vault_account": self.counterfeit_vault_pk,
            "official_vault_account": self.official_vault_pk,
        }

    def _derive_keypair(self, role: str) -> Keypair:
        # Keep the original runtime namespace stable so existing session IDs replay to
        # the same deterministic accounts even though the learner-facing lab identity is RL1.
        msg = f"treasury-mirage|v1|{self.session_id}|{role}".encode()
        return Keypair.from_seed(hmac.new(self._secret, msg, hashlib.sha256).digest()[:32])

    async def materialize(self, load_program: bool = True) -> LiteSVM:
        t0 = time.time()
        svm = LiteSVM()

        if load_program:
            so_path = (
                self.template_root
                / resolve_lab_template_ref("research-labs/account-substitution@v1")
                / "treasury_mirage.so"
            )
            resolved = str(so_path.resolve())
            print(f"[solbreach] program .so path: {resolved}, exists: {so_path.exists()}")
            if so_path.exists():
                with open(so_path, "rb") as f:
                    svm.add_program(PROGRAM_ID, f.read())
                    print(f"[solbreach] program loaded: {PROGRAM_ID}")
            else:
                print(f"[solbreach] program NOT FOUND at {resolved}")

        self.metrics["boot_and_load_ms"] = (time.time() - t0) * 1000

        svm.set_account(
            self.payer.pubkey(),
            Account(lamports=10_000_000_000, data=b"", owner=SYS_PROGRAM_ID, executable=False, rent_epoch=0),
        )
        svm.set_account(
            self.attacker.pubkey(),
            Account(lamports=INITIAL_REWARD_LAMPORTS, data=b"", owner=SYS_PROGRAM_ID, executable=False, rent_epoch=0),
        )
        svm.set_account(
            self.treasury_pda,
            Account(lamports=INITIAL_TREASURY_LAMPORTS, data=b"", owner=PROGRAM_ID, executable=False, rent_epoch=0),
        )
        svm.set_account(
            self.attacker_collateral_pk,
            Account(
                lamports=1_000_000,
                data=_spl_token_data(self.counterfeit_mint, self.attacker.pubkey(), COUNTERFEIT_COLLATERAL_START),
                owner=TOKEN_PROGRAM_ID,
                executable=False,
                rent_epoch=0,
            ),
        )
        svm.set_account(
            self.official_collateral_pk,
            Account(
                lamports=1_000_000,
                data=_spl_token_data(self.official_mint, self.attacker.pubkey(), OFFICIAL_COLLATERAL_START),
                owner=TOKEN_PROGRAM_ID,
                executable=False,
                rent_epoch=0,
            ),
        )
        svm.set_account(
            self.counterfeit_vault_pk,
            Account(
                lamports=1_000_000,
                data=_spl_token_data(self.counterfeit_mint, self.treasury_pda, 0),
                owner=TOKEN_PROGRAM_ID,
                executable=False,
                rent_epoch=0,
            ),
        )
        svm.set_account(
            self.official_vault_pk,
            Account(
                lamports=1_000_000,
                data=_spl_token_data(self.official_mint, self.treasury_pda, 1_000_000),
                owner=TOKEN_PROGRAM_ID,
                executable=False,
                rent_epoch=0,
            ),
        )

        init_ix = Instruction(
            PROGRAM_ID,
            _discriminator("global", "initialize"),
            [
                AccountMeta(self.position_pda, False, True),
                AccountMeta(self.attacker.pubkey(), True, True),
                AccountMeta(SYS_PROGRAM_ID, False, False),
            ],
        )
        bh = svm.latest_blockhash()
        tx = VersionedTransaction(Message.new_with_blockhash([init_ix], self.payer.pubkey(), bh), [self.payer, self.attacker])
        svm.send_transaction(tx)

        t_seed = time.time()
        self.metrics["seed_state_ms"] = (t_seed - t0) * 1000

        try:
            result = await self.db_session.execute(
                select(ResearchLabTransactionModel)
                .where(ResearchLabTransactionModel.session_id == self.session_id)
                .where(ResearchLabTransactionModel.execution_status == "success")
                .order_by(ResearchLabTransactionModel.sequence_number.asc())
            )
            tx_models = result.scalars().all()
        except Exception:
            tx_models = []
            await self.db_session.rollback()
        for tx_model in tx_models:
            self._execute_structured(svm, tx_model.instruction_type, tx_model.parameters_json)

        self.metrics["replay_ms"] = (time.time() - t_seed) * 1000
        return svm

    def _execute_structured(self, svm: LiteSVM, action_type: str, params: dict):
        ix = None
        position_credit_override: int | None = None
        if action_type == "DEPOSIT_COLLATERAL":
            amount = int(params.get("amount") or 0)
            collat_ref = params.get("collateral_account_ref", "attacker_collateral")
            vault_ref = params.get("vault_account_ref", "counterfeit_vault")

            if collat_ref in ("attacker_collateral", "attacker_collateral_account", "candidate_collateral", "candidate_collateral_account"):
                source = self.attacker_collateral_pk
                source_acc = svm.get_account(source)
                current_credit = _position_credit(svm.get_account(self.position_pda).data)
                exploit_credit = _token_amount(source_acc.data) if source_acc else 0
                position_credit_override = current_credit + exploit_credit
            elif collat_ref in ("official_collateral", "official_collateral_account"):
                source = self.official_collateral_pk
                current_credit = _position_credit(svm.get_account(self.position_pda).data)
                position_credit_override = current_credit + min(amount, OFFICIAL_COLLATERAL_START)
            else:
                return None

            if vault_ref in ("counterfeit_vault", "counterfeit_vault_account", "external_vault", "external_vault_account"):
                dest = self.counterfeit_vault_pk
            elif vault_ref in ("official_vault", "official_vault_account"):
                dest = self.official_vault_pk
            else:
                return None

            ix = Instruction(
                PROGRAM_ID,
                _discriminator("global", "deposit_collateral") + amount.to_bytes(8, "little"),
                [
                    AccountMeta(self.position_pda, False, True),
                    AccountMeta(source, False, True),
                    AccountMeta(dest, False, True),
                    AccountMeta(self.attacker.pubkey(), True, True),
                    AccountMeta(TOKEN_PROGRAM_ID, False, False),
                ],
            )
        elif action_type == "WITHDRAW_AGAINST_CREDIT":
            position_acc = svm.get_account(self.position_pda)
            credited_collateral = _position_credit(position_acc.data) if position_acc else 0
            treasury_acc = svm.get_account(self.treasury_pda)
            treasury_lamports = treasury_acc.lamports if treasury_acc else 0
            reward_acc = svm.get_account(self.attacker.pubkey())
            borrowed_total = max((reward_acc.lamports if reward_acc else 0) - INITIAL_REWARD_LAMPORTS, 0)
            quote = _borrow_quote(credited_collateral, treasury_lamports, borrowed_total)
            amount = int(params.get("amount", quote["availableBorrow"]))
            if amount <= 0 or amount > int(quote["availableBorrow"]):
                return None
            ix = Instruction(
                PROGRAM_ID,
                _discriminator("global", "withdraw_against_credit") + amount.to_bytes(8, "little"),
                [
                    AccountMeta(self.position_pda, False, True),
                    AccountMeta(self.treasury_pda, False, True),
                    AccountMeta(self.attacker.pubkey(), False, True),
                    AccountMeta(self.attacker.pubkey(), True, True),
                    AccountMeta(SYS_PROGRAM_ID, False, False),
                ],
            )

        if ix:
            bh = svm.latest_blockhash()
            tx = VersionedTransaction(Message.new_with_blockhash([ix], self.payer.pubkey(), bh), [self.payer, self.attacker])
            result = svm.send_transaction(tx)
            if not isinstance(result, FailedTransactionMetadata) and position_credit_override is not None:
                _set_position_credit(svm, self.position_pda, position_credit_override)
            return result
        return None


class LiteSVMSandboxRuntime(SandboxRuntime):
    def __init__(self, template_root: Path, workspace_root: Path, db_session: AsyncSession = None) -> None:
        self._template_root = template_root
        self._workspace_root = workspace_root
        self._db_session = db_session

    async def create_session(self, session_id: str, template_ref: str) -> str:
        return session_id

    async def hydrate_template(self, session_id: str, template_ref: str) -> None:
        pass

    async def read_file(self, session_id: str, path: str) -> str:
        file_path = (
            self._template_root
            / resolve_lab_template_ref("research-labs/account-substitution@v1")
            / resolve_lab_file_path(path)
        ).resolve()
        if file_path.exists() and file_path.is_file():
            return file_path.read_text(encoding="utf-8")
        return ""

    async def patch_file(self, session_id: str, path: str, content: str) -> None:
        pass

    async def run_tests(self, session_id: str, command: str, timeout_seconds: int) -> SandboxTestRunResult:
        return SandboxTestRunResult(status="passed", exit_code=0)

    async def reset_session(self, session_id: str, template_ref: str) -> None:
        pass

    async def destroy_session(self, session_id: str) -> None:
        pass

    async def get_visible_accounts(self, session_id: str) -> list[SandboxAccountSummary]:
        mat = SessionMaterializer(self._template_root, self._db_session, session_id)
        svm = await mat.materialize()
        tx_result = await self._db_session.execute(
            select(ResearchLabTransactionModel)
            .where(ResearchLabTransactionModel.session_id == session_id)
            .order_by(ResearchLabTransactionModel.sequence_number.asc())
        )
        tx_models = list(tx_result.scalars().all())

        def _lamports(pk: Pubkey) -> int:
            acc = svm.get_account(pk)
            return acc.lamports if acc else 0

        position_acc = svm.get_account(mat.position_pda)
        credited_collateral = _position_credit(position_acc.data) if position_acc else 0
        treasury_lamports = _lamports(mat.treasury_pda)
        reward_lamports = _lamports(mat.attacker.pubkey())
        protocol_state = _derive_protocol_state(
            tx_models,
            credited_collateral,
            treasury_lamports,
            reward_lamports,
        )

        return [
            SandboxAccountSummary("treasury_vault", "Protocol Treasury", str(PROGRAM_ID), treasury_lamports, {
                "availableBorrow": protocol_state["availableBorrow"],
                "maxBorrow": protocol_state["maxBorrow"],
            }),
            SandboxAccountSummary("position", "Borrow Position", str(PROGRAM_ID), 0, {
                "creditedCollateral": credited_collateral,
                "borrowedTotal": protocol_state["borrowedTotal"],
                "availableBorrow": protocol_state["availableBorrow"],
                "maxBorrow": protocol_state["maxBorrow"],
                "depositPathType": protocol_state["depositPathType"],
                "borrowAllowed": protocol_state["borrowAllowed"],
                "ltvBps": protocol_state["ltvBps"],
            }),
            SandboxAccountSummary("attacker_reward_account", "Learner Reward Wallet", str(SYS_PROGRAM_ID), reward_lamports, {
                "borrowedTotal": protocol_state["borrowedTotal"],
            }),
            SandboxAccountSummary("counterfeit_mint_account", "Counterfeit Mint", str(TOKEN_PROGRAM_ID), 0, {"approved": False}),
            SandboxAccountSummary("official_mint_account", "Official Mint", str(TOKEN_PROGRAM_ID), 0, {"approved": True}),
            SandboxAccountSummary("attacker_collateral_account", "Candidate Collateral Account", str(TOKEN_PROGRAM_ID), _lamports(mat.attacker_collateral_pk), {
                "tokenAmount": COUNTERFEIT_COLLATERAL_START,
                "approved": False,
            }),
            SandboxAccountSummary("official_collateral_account", "Official Collateral Account", str(TOKEN_PROGRAM_ID), _lamports(mat.official_collateral_pk), {
                "tokenAmount": OFFICIAL_COLLATERAL_START,
                "approved": True,
            }),
            SandboxAccountSummary("counterfeit_vault_account", "External Vault", str(TOKEN_PROGRAM_ID), _lamports(mat.counterfeit_vault_pk), {"approved": False}),
            SandboxAccountSummary("official_vault_account", "Official Vault", str(TOKEN_PROGRAM_ID), _lamports(mat.official_vault_pk), {"approved": True}),
        ]

    async def get_account_state(self, session_id: str, account_ref: str) -> SandboxAccountSnapshot:
        mat = SessionMaterializer(self._template_root, self._db_session, session_id)
        svm = await mat.materialize()
        tx_result = await self._db_session.execute(
            select(ResearchLabTransactionModel)
            .where(ResearchLabTransactionModel.session_id == session_id)
            .order_by(ResearchLabTransactionModel.sequence_number.asc())
        )
        tx_models = list(tx_result.scalars().all())

        def _pk(acct_name: str) -> Pubkey | None:
            info = LAB_ACCOUNT_MAP.get(acct_name)
            if not info:
                return None
            if info.get("pda"):
                if acct_name in ("treasury", "treasury_vault"):
                    return mat.treasury_pda
                if acct_name == "position":
                    return mat.position_pda
            role = info.get("key_role")
            if not role:
                return None
            return mat._derive_keypair(role).pubkey() if role else None

        pk = _pk(account_ref)
        if not pk:
            raise NotFoundError(f"Unknown account: {account_ref}")

        acc = svm.get_account(pk)
        if not acc:
            raise NotFoundError(f"Account not found in sandbox: {account_ref}")

        data = {}
        if str(acc.owner) == str(TOKEN_PROGRAM_ID) and len(acc.data) >= 165:
            raw = acc.data
            data["mint"] = str(Pubkey.from_bytes(raw[0:32]))
            data["owner"] = str(Pubkey.from_bytes(raw[32:64]))
            data["amount"] = int.from_bytes(raw[64:72], "little")
            data["approved"] = account_ref in {
                "official_collateral_account",
                "official_vault_account",
                "official_mint_account",
            }
        elif account_ref == "position":
            credited_collateral = _position_credit(acc.data)
            treasury_acc = svm.get_account(mat.treasury_pda)
            treasury_lamports = treasury_acc.lamports if treasury_acc else 0
            reward_acc = svm.get_account(mat.attacker.pubkey())
            reward_lamports = reward_acc.lamports if reward_acc else 0
            data.update(
                _derive_protocol_state(
                    tx_models,
                    credited_collateral,
                    treasury_lamports,
                    reward_lamports,
                )
            )
        elif account_ref == "treasury_vault":
            position_acc = svm.get_account(mat.position_pda)
            credited_collateral = _position_credit(position_acc.data) if position_acc else 0
            reward_acc = svm.get_account(mat.attacker.pubkey())
            reward_lamports = reward_acc.lamports if reward_acc else 0
            data.update(
                _derive_protocol_state(
                    tx_models,
                    credited_collateral,
                    acc.lamports,
                    reward_lamports,
                )
            )
        elif account_ref == "attacker_reward_account":
            position_acc = svm.get_account(mat.position_pda)
            credited_collateral = _position_credit(position_acc.data) if position_acc else 0
            treasury_acc = svm.get_account(mat.treasury_pda)
            treasury_lamports = treasury_acc.lamports if treasury_acc else 0
            data.update(
                _derive_protocol_state(
                    tx_models,
                    credited_collateral,
                    treasury_lamports,
                    acc.lamports,
                )
            )

        return SandboxAccountSnapshot(
            ref=account_ref,
            label=LAB_ACCOUNT_MAP.get(account_ref, {}).get("label", account_ref),
            owner=str(acc.owner),
            lamports=acc.lamports,
            data=data,
        )

    async def submit_transaction(
        self, session_id: str, action_type: str, parameters: dict
    ) -> SandboxTransactionResult:
        mat = SessionMaterializer(self._template_root, self._db_session, session_id)
        svm = await mat.materialize()
        tracked_refs = [
            "treasury_vault",
            "position",
            "attacker_reward_account",
            "attacker_collateral_account",
            "official_collateral_account",
            "counterfeit_vault_account",
            "official_vault_account",
        ]
        before = _snapshot_accounts(svm, mat, tracked_refs)
        t0 = time.time()
        result = mat._execute_structured(svm, action_type, parameters)
        _ = time.time() - t0
        tx_history: list[ResearchLabTransactionModel | SimpleNamespace] = []
        if self._db_session is not None:
            history_result = await self._db_session.execute(
                select(ResearchLabTransactionModel)
                .where(ResearchLabTransactionModel.session_id == session_id)
                .where(ResearchLabTransactionModel.execution_status == "success")
                .order_by(ResearchLabTransactionModel.sequence_number.asc())
            )
            tx_history = list(history_result.scalars().all())

        success = False
        logs = []
        account_deltas: list[dict] = []
        protocol_state: dict = {}
        user_msg = "Transaction failed."
        if result is None:
            if action_type == "WITHDRAW_AGAINST_CREDIT":
                user_msg = "Borrow request exceeds the currently available borrow limit."
            else:
                user_msg = "Unknown or invalid action parameters."
        elif isinstance(result, FailedTransactionMetadata):
            err = result.err()
            meta = result.meta()
            logs = list(meta.logs())
            err_str = str(err) if err else "unknown error"
            user_msg = f"Transaction failed: {err_str}"
        else:
            success = True
            logs = list(result.logs())
            after = _snapshot_accounts(svm, mat, tracked_refs)
            account_deltas = _build_account_deltas(before, after)
            position_acc = svm.get_account(mat.position_pda)
            credited_collateral = _position_credit(position_acc.data) if position_acc else 0
            treasury_acc = svm.get_account(mat.treasury_pda)
            treasury_lamports = treasury_acc.lamports if treasury_acc else 0
            reward_acc = svm.get_account(mat.attacker.pubkey())
            reward_lamports = reward_acc.lamports if reward_acc else 0
            tx_history = [
                *tx_history,
                SimpleNamespace(
                    transaction_ref=f"tx_preview_{uuid4().hex[:8]}",
                    sequence_number=len(tx_history) + 1,
                    execution_status="success",
                    instruction_type=action_type,
                    parameters_json=parameters,
                ),
            ]
            protocol_state = _derive_protocol_state(
                tx_history,
                credited_collateral,
                treasury_lamports,
                reward_lamports,
            )
            user_msg = "Transaction submitted."

        if not protocol_state:
            position_acc = svm.get_account(mat.position_pda)
            credited_collateral = _position_credit(position_acc.data) if position_acc else 0
            treasury_acc = svm.get_account(mat.treasury_pda)
            treasury_lamports = treasury_acc.lamports if treasury_acc else 0
            reward_acc = svm.get_account(mat.attacker.pubkey())
            reward_lamports = reward_acc.lamports if reward_acc else 0
            protocol_state = _derive_protocol_state(
                tx_history,
                credited_collateral,
                treasury_lamports,
                reward_lamports,
            )

        return SandboxTransactionResult(
            transaction_ref=f"tx_{uuid4().hex[:16]}",
            instruction_type=action_type,
            execution_status="success" if success else "failure",
            logs=logs,
            account_deltas=account_deltas,
            protocol_state=protocol_state,
            user_facing_evidence=[user_msg],
        )

    async def get_transaction_logs(self, session_id: str, transaction_ref: str) -> list[str]:
        if not self._db_session:
            return []
        result = await self._db_session.execute(
            select(ResearchLabTransactionModel)
            .where(ResearchLabTransactionModel.session_id == session_id)
            .where(ResearchLabTransactionModel.transaction_ref == transaction_ref)
        )
        tx = result.scalar_one_or_none()
        return tx.logs_json if tx else []

    async def verify_objective(self, session_id: str, objective_ref: str) -> SandboxVerificationResult:
        mat = SessionMaterializer(self._template_root, self._db_session, session_id)
        svm = await mat.materialize()

        treasury_acc = svm.get_account(mat.treasury_pda)
        treasury_lamports = treasury_acc.lamports if treasury_acc else INITIAL_TREASURY_LAMPORTS

        position_acc = svm.get_account(mat.position_pda)
        if position_acc and len(position_acc.data) >= 48:
            credited = int.from_bytes(position_acc.data[8 + 32 : 8 + 32 + 8], "little")
        else:
            credited = 0

        attacker_acc = svm.get_account(mat.attacker.pubkey())
        attacker_lamports = attacker_acc.lamports if attacker_acc else 0

        result = await self._db_session.execute(
            select(ResearchLabTransactionModel)
            .where(ResearchLabTransactionModel.session_id == session_id)
            .order_by(ResearchLabTransactionModel.sequence_number.asc())
        )
        tx_models = list(result.scalars().all())

        protocol_state = _derive_protocol_state(
            tx_models,
            credited,
            treasury_lamports,
            attacker_lamports,
        )

        successful_invalid_deposit = None
        successful_official_deposit = None
        successful_withdrawal = None
        for tx_model in tx_models:
            if tx_model.execution_status != "success":
                continue
            if tx_model.instruction_type == "DEPOSIT_COLLATERAL":
                collateral_ref = tx_model.parameters_json.get("collateral_account_ref")
                vault_ref = tx_model.parameters_json.get("vault_account_ref")
                path_type = _deposit_path_type(collateral_ref, vault_ref)
                if path_type == "exploit":
                    successful_invalid_deposit = tx_model
                elif path_type == "official":
                    successful_official_deposit = tx_model
            if tx_model.instruction_type == "WITHDRAW_AGAINST_CREDIT" and tx_model.execution_status == "success":
                successful_withdrawal = tx_model

        counterfeit_deposit_observed = successful_invalid_deposit is not None
        unapproved_collateral_source_used = counterfeit_deposit_observed
        non_canonical_vault_destination_used = counterfeit_deposit_observed
        position_credit_increased = counterfeit_deposit_observed and credited > 0
        treasury_drained = treasury_lamports < INITIAL_TREASURY_LAMPORTS
        withdrawal_observed = successful_withdrawal is not None
        exploit_provenance_confirmed = (
            successful_invalid_deposit is not None
            and successful_withdrawal is not None
            and successful_invalid_deposit.sequence_number < successful_withdrawal.sequence_number
        )
        real_protocol_treasury_value_decreased = treasury_drained
        official_path_used = successful_official_deposit is not None
        exploit_path_only = protocol_state["depositPathType"] == "exploit"
        borrowed_total = int(protocol_state["borrowedTotal"])
        max_borrow = int(protocol_state["maxBorrow"])
        available_borrow = int(protocol_state["availableBorrow"])
        max_drain_satisfied = borrowed_total > 0 and available_borrow == 0
        legitimate_official_borrow_only = (
            official_path_used
            and successful_invalid_deposit is None
            and withdrawal_observed
        )

        passed = all(
            [
                counterfeit_deposit_observed,
                unapproved_collateral_source_used,
                non_canonical_vault_destination_used,
                position_credit_increased,
                withdrawal_observed,
                real_protocol_treasury_value_decreased,
                exploit_provenance_confirmed,
                exploit_path_only,
                max_drain_satisfied,
            ]
        )
        verified_evidence_refs = []
        if successful_invalid_deposit is not None:
            verified_evidence_refs.append(f"transaction:{successful_invalid_deposit.transaction_ref}")
        if successful_withdrawal is not None:
            verified_evidence_refs.append(f"transaction:{successful_withdrawal.transaction_ref}")
        if treasury_drained:
            verified_evidence_refs.append("account:treasury_vault")
        if successful_invalid_deposit is not None:
            verified_evidence_refs.append("account:position")

        evidence = {
            "transactionTimeline": [
                {
                    "transactionRef": tx_model.transaction_ref,
                    "instructionType": tx_model.instruction_type,
                    "executionStatus": tx_model.execution_status,
                    "sequenceNumber": tx_model.sequence_number,
                    "evidenceRefs": tx_model.evidence_refs_json,
                }
                for tx_model in tx_models
            ],
            "accountDeltas": [
                delta
                for tx_model in tx_models
                for delta in (tx_model.account_deltas_json or [])
            ],
            "runtimeLogs": [
                {
                    "transactionRef": tx_model.transaction_ref,
                    "logs": tx_model.logs_json,
                }
                for tx_model in tx_models
            ],
            "impactChecklist": {
                "counterfeitDepositObserved": counterfeit_deposit_observed,
                "unapprovedCollateralSourceUsed": unapproved_collateral_source_used,
                "nonCanonicalVaultDestinationUsed": non_canonical_vault_destination_used,
                "positionCreditIncreasedFromInvalidRelationship": position_credit_increased,
                "withdrawOrBorrowAgainstInvalidCreditObserved": withdrawal_observed,
                "realProtocolTreasuryValueDecreased": real_protocol_treasury_value_decreased,
                "exploitProvenanceConfirmed": exploit_provenance_confirmed,
                "officialPathUsed": official_path_used,
                "exploitPathOnly": exploit_path_only,
                "maxDrainSatisfied": max_drain_satisfied,
            },
            "protocolState": protocol_state,
            "treasuryLamportsBefore": INITIAL_TREASURY_LAMPORTS,
            "treasuryLamportsAfter": treasury_lamports,
            "creditedCollateralBefore": 0,
            "creditedCollateralAfter": credited,
            "borrowedAmount": borrowed_total,
            "maxBorrowAmount": max_borrow,
            "availableBorrowAfter": available_borrow,
            "attackerLamportsIncrease": attacker_lamports - INITIAL_REWARD_LAMPORTS,
        }

        failure_reason = None
        if not passed:
            if not counterfeit_deposit_observed:
                failure_reason = "No invalid collateral-to-vault deposit has been observed."
            elif legitimate_official_borrow_only:
                failure_reason = "Observed borrow came from the official collateral path, not the exploit path."
            elif not withdrawal_observed:
                failure_reason = "No treasury withdrawal against invalid credit has been observed."
            elif not real_protocol_treasury_value_decreased:
                failure_reason = "Treasury value did not decrease."
            elif not exploit_path_only:
                failure_reason = "Exploit provenance is ambiguous because both official and exploit paths were used."
            elif not max_drain_satisfied:
                failure_reason = (
                    f"Exploit path was used, but the treasury was not drained to the backend-computed max borrow "
                    f"amount ({max_borrow})."
                )
            else:
                failure_reason = "Exploit provenance requirements were not satisfied."

        user_facing = (
            [
                "Invalid account substitution created protocol credit.",
                "Verified treasury value movement occurred after the invalid credit was used.",
                f"Exploit drain matched the backend max-borrow quote ({max_borrow}).",
            ]
            if passed
            else [failure_reason or "No verified unauthorized treasury withdrawal has been observed."]
        )

        return SandboxVerificationResult(
            objective_ref=objective_ref,
            passed=passed,
            evidence=evidence,
            verified_evidence_refs=verified_evidence_refs,
            failure_reason=failure_reason,
            user_facing_evidence=user_facing,
        )
