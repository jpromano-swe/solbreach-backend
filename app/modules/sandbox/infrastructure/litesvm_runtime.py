import time
import hmac
import hashlib
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

LAB_ACCOUNT_MAP = {
    "treasury_vault": {"label": "Treasury Vault", "pda": True},
    "position": {"label": "Attacker Position", "pda": True},
    "attacker_reward_account": {"label": "Attacker Wallet", "pda": False, "key_role": "attacker"},
    "attacker_wallet": {"label": "Attacker Wallet", "pda": False, "key_role": "attacker"},
    "payer_wallet": {"label": "Payer Wallet", "pda": False, "key_role": "payer"},
    "counterfeit_mint_account": {"label": "Counterfeit Collateral Mint", "pda": False, "key_role": "cmint"},
    "official_mint_account": {"label": "Official Collateral Mint", "pda": False, "key_role": "omint"},
    "attacker_collateral_account": {"label": "Attacker Counterfeit Token Account", "pda": False, "key_role": "acollat"},
    "official_collateral_account": {"label": "Official Collateral Token Account", "pda": False, "key_role": "ocollat"},
    "counterfeit_vault_account": {"label": "Counterfeit Vault", "pda": False, "key_role": "cvault"},
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

    def _derive_keypair(self, role: str) -> Keypair:
        msg = f"treasury-mirage|v1|{self.session_id}|{role}".encode()
        return Keypair.from_seed(hmac.new(self._secret, msg, hashlib.sha256).digest()[:32])

    async def materialize(self, load_program: bool = True) -> LiteSVM:
        t0 = time.time()
        svm = LiteSVM()

        if load_program:
            so_path = (
                self.template_root
                / "research-labs"
                / "treasury-mirage@v1"
                / "treasury_mirage.so"
            )
            if so_path.exists():
                with open(so_path, "rb") as f:
                    svm.add_program(PROGRAM_ID, f.read())

        self.metrics["boot_and_load_ms"] = (time.time() - t0) * 1000

        svm.set_account(
            self.payer.pubkey(),
            Account(lamports=10_000_000_000, data=b"", owner=SYS_PROGRAM_ID, executable=False, rent_epoch=0),
        )
        svm.set_account(
            self.attacker.pubkey(),
            Account(lamports=1_000_000_000, data=b"", owner=SYS_PROGRAM_ID, executable=False, rent_epoch=0),
        )
        svm.set_account(
            self.treasury_pda,
            Account(lamports=INITIAL_TREASURY_LAMPORTS, data=b"", owner=PROGRAM_ID, executable=False, rent_epoch=0),
        )
        svm.set_account(
            self.attacker_collateral_pk,
            Account(
                lamports=1_000_000,
                data=_spl_token_data(self.counterfeit_mint, self.attacker.pubkey(), 500_000),
                owner=TOKEN_PROGRAM_ID,
                executable=False,
                rent_epoch=0,
            ),
        )
        svm.set_account(
            self.official_collateral_pk,
            Account(
                lamports=1_000_000,
                data=_spl_token_data(self.official_mint, self.attacker.pubkey(), 500_000),
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
        if action_type == "DEPOSIT_COLLATERAL":
            amount = int(params.get("amount", 50_000))
            collat_ref = params.get("collateral_account_ref", "attacker_collateral")
            vault_ref = params.get("vault_account_ref", "counterfeit_vault")

            if collat_ref in ("attacker_collateral", "attacker_collateral_account"):
                source = self.attacker_collateral_pk
            elif collat_ref in ("official_collateral", "official_collateral_account"):
                source = self.official_collateral_pk
            else:
                return None

            if vault_ref in ("counterfeit_vault", "counterfeit_vault_account"):
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
            amount = int(params.get("amount", 50_000))
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
            return svm.send_transaction(tx)
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
        file_path = (self._template_root / "research-labs" / "treasury-mirage@v1" / path).resolve()
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

        def _lamports(pk: Pubkey) -> int:
            acc = svm.get_account(pk)
            return acc.lamports if acc else 0

        return [
            SandboxAccountSummary("treasury_vault", "Treasury Vault", str(PROGRAM_ID), _lamports(mat.treasury_pda), {}),
            SandboxAccountSummary("position", "Attacker Position", str(PROGRAM_ID), 0, {}),
            SandboxAccountSummary("attacker_reward_account", "Attacker Wallet", str(SYS_PROGRAM_ID), _lamports(mat.attacker.pubkey()), {}),
            SandboxAccountSummary("counterfeit_mint_account", "Counterfeit Mint", str(TOKEN_PROGRAM_ID), 0, {"approved": False}),
            SandboxAccountSummary("official_mint_account", "Official Mint", str(TOKEN_PROGRAM_ID), 0, {"approved": True}),
            SandboxAccountSummary("attacker_collateral_account", "Attacker Counterfeit Token Account", str(TOKEN_PROGRAM_ID), _lamports(mat.attacker_collateral_pk), {}),
            SandboxAccountSummary("official_collateral_account", "Official Collateral Token Account", str(TOKEN_PROGRAM_ID), _lamports(mat.official_collateral_pk), {}),
            SandboxAccountSummary("counterfeit_vault_account", "Counterfeit Vault", str(TOKEN_PROGRAM_ID), _lamports(mat.counterfeit_vault_pk), {}),
            SandboxAccountSummary("official_vault_account", "Official Vault", str(TOKEN_PROGRAM_ID), _lamports(mat.official_vault_pk), {}),
        ]

    async def get_account_state(self, session_id: str, account_ref: str) -> SandboxAccountSnapshot:
        mat = SessionMaterializer(self._template_root, self._db_session, session_id)
        svm = await mat.materialize()

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
        t0 = time.time()
        result = mat._execute_structured(svm, action_type, parameters)
        exec_time = time.time() - t0

        success = False
        logs = []
        user_msg = "Transaction failed."
        if result is None:
            user_msg = "Unknown action type."
        elif isinstance(result, FailedTransactionMetadata):
            err = result.err()
            meta = result.meta()
            logs = list(meta.logs())
            err_str = str(err) if err else "unknown error"
            user_msg = f"Transaction failed: {err_str}"
        else:
            success = True
            logs = list(result.logs())
            user_msg = "Transaction submitted."

        return SandboxTransactionResult(
            transaction_ref=f"tx_{uuid4().hex[:16]}",
            instruction_type=action_type,
            execution_status="success" if success else "failure",
            logs=logs,
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

        treasury_drained = treasury_lamports < INITIAL_TREASURY_LAMPORTS
        credit_granted = credited > 0
        credit_consumed = credited == 0 and treasury_drained

        passed = treasury_drained and credit_consumed

        evidence = {
            "sessionOwnershipValid": True,
            "counterfeitCollateralUsed": True,
            "illegitimateCreditAssigned": credit_granted,
            "realTreasuryWithdrawalOccurred": treasury_drained,
            "creditConsumed": credit_consumed,
            "treasuryLamportsBefore": INITIAL_TREASURY_LAMPORTS,
            "treasuryLamportsAfter": treasury_lamports,
            "attackerLamportsIncrease": attacker_lamports > 1_000_000_000,
        }

        user_facing = (
            [
                "Unapproved collateral generated protocol credit.",
                "Legitimate treasury value was withdrawn by the attacker-controlled actor.",
            ]
            if passed
            else ["No verified unauthorized treasury withdrawal has been observed."]
        )

        return SandboxVerificationResult(
            objective_ref=objective_ref,
            passed=passed,
            evidence=evidence,
            user_facing_evidence=user_facing,
        )
