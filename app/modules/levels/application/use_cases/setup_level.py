import hashlib
import logging
from datetime import UTC, datetime
from typing import Any

from app.core.exceptions.domain import ConflictError, ForbiddenError
from app.modules.levels.application.dto.level_gameplay import LevelSetupResult
from app.modules.levels.application.use_cases.get_level import LevelNotFoundError
from app.modules.levels.application.use_cases.start_level import LevelLockedError
from app.modules.levels.application.use_cases.submit_level import LevelNotStartedError
from app.modules.levels.domain.entities.level import Level
from app.modules.levels.domain.entities.level_session import ExploitStatus, LevelState
from app.modules.levels.domain.repositories.level_repository import LevelRepository
from app.modules.levels.domain.repositories.level_session_repository import LevelSessionRepository
from app.modules.levels.domain.services.level_access import LevelAccessService
from app.modules.users.domain.entities.user import User

BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
logger = logging.getLogger(__name__)


class LevelSetupAlreadyBoundError(ConflictError):
    code = "LEVEL_SETUP_ALREADY_BOUND"


class LevelSetupUnavailableError(ConflictError):
    code = "LEVEL_SETUP_UNAVAILABLE"


class WalletOwnershipError(ForbiddenError):
    code = "WALLET_OWNERSHIP_REQUIRED"


class SetupLevelUseCase:
    def __init__(
        self,
        levels: LevelRepository,
        sessions: LevelSessionRepository,
        access: LevelAccessService,
    ) -> None:
        self._levels = levels
        self._sessions = sessions
        self._access = access

    async def execute(self, user: User, level_id: str, wallet_address: str) -> LevelSetupResult:
        user_id = user.id
        if user.wallet_address is not None and user.wallet_address != wallet_address:
            raise WalletOwnershipError("Connected wallet does not belong to this user")

        level = await self._levels.get_by_id(level_id)
        if level is None:
            raise LevelNotFoundError("Level not found")

        latest_session = await self._sessions.get_latest(user_id, level_id)
        state, _ = await self._access.state_for(user_id, level, latest_session)
        if state == LevelState.LOCKED:
            raise LevelLockedError("Complete the previous level before starting this one")

        session = await self._sessions.get_active(user_id, level_id)
        if session is None:
            raise LevelNotStartedError("Start the level before setup")

        if session.wallet_address and session.wallet_address != wallet_address:
            raise LevelSetupAlreadyBoundError("Level session is already bound to another wallet")

        if session.challenge_context:
            logger.info(
                "level_setup_resumed",
                extra={
                    "user_id": user_id,
                    "level_id": level_id,
                    "session_id": session.id,
                    "wallet_address": wallet_address,
                },
            )
            return LevelSetupResult(
                level=level,
                session=session,
                challenge=session.challenge_context,
                exploit_status=session.exploit_status.value,
            )

        challenge = _build_challenge(level, session.id, wallet_address)
        session.wallet_address = wallet_address
        session.challenge_context = challenge
        session.setup_at = datetime.now(UTC)
        session.exploit_status = ExploitStatus.SETUP_READY
        session = await self._sessions.update(session)
        logger.info(
            "level_setup_ready",
            extra={
                "user_id": user_id,
                "level_id": level_id,
                "session_id": session.id,
                "wallet_address": wallet_address,
                "network": challenge["network"],
            },
        )
        return LevelSetupResult(
            level=level,
            session=session,
            challenge=challenge,
            exploit_status=session.exploit_status.value,
        )


def _build_challenge(level: Level, level_session_id: str, wallet_address: str) -> dict[str, Any]:
    execution = level.deployment_info.get("execution") or {}
    if execution.get("enabled") is not True:
        raise LevelSetupUnavailableError("This level does not expose exploit setup")

    challenge_type = str(execution.get("challenge_type", "fake_mint"))
    if challenge_type == "fake_mint":
        return _build_level_1_challenge(level, level_session_id, wallet_address, execution)
    if challenge_type == "static_pda_commander_hijack":
        return _build_level_2_challenge(level, level_session_id, wallet_address, execution)
    if challenge_type == "arbitrary_cpi_delegated_signer_abuse":
        return _build_level_3_challenge(level, level_session_id, wallet_address, execution)
    if challenge_type == "data_matching":
        return _build_level_4_challenge(level, level_session_id, wallet_address, execution)
    if challenge_type == "address_reuse_pda_lifecycle":
        return _build_level_5_challenge(level, level_session_id, wallet_address, execution)
    raise LevelSetupUnavailableError("This level does not expose a supported exploit setup")


def _build_level_1_challenge(
    level: Level,
    level_session_id: str,
    wallet_address: str,
    execution: dict[str, Any],
) -> dict[str, Any]:
    network = str(execution.get("network", "devnet"))
    program_id = str(execution.get("program_id", _pubkey(level_session_id, "program")))
    official_mint = str(execution.get("official_mint", _pubkey(level_session_id, "official_mint")))
    official_vault = str(
        execution.get("official_vault", _pubkey(level_session_id, "official_vault"))
    )
    fake_mint = _pubkey(level_session_id, wallet_address, "fake_mint")
    fake_vault = _pubkey(level_session_id, wallet_address, "fake_vault")
    challenge_pda = _pubkey(level_session_id, wallet_address, "challenge_pda")
    attacker_token_account = _pubkey(level_session_id, wallet_address, "attacker_token_account")
    required_accounts = [
        program_id,
        official_mint,
        official_vault,
        fake_mint,
        fake_vault,
        challenge_pda,
        attacker_token_account,
        wallet_address,
    ]
    return {
        "network": network,
        "level_session_id": level_session_id,
        "wallet_address": wallet_address,
        "program_id": program_id,
        "official_mint": official_mint,
        "official_vault": official_vault,
        "fake_mint": fake_mint,
        "fake_vault": fake_vault,
        "challenge_pda": challenge_pda,
        "attacker_token_account": attacker_token_account,
        "required_accounts": required_accounts,
        "required_pdas": [
            {
                "label": "challenge_pda",
                "address": challenge_pda,
                "seeds": ["solbreach", level.slug, level_session_id],
            }
        ],
        "exploit_parameters": {
            "vulnerability": "fake_mint",
            "mode": str(execution.get("mode", "wallet_signed_demo_transaction")),
            "demo_mode": bool(execution.get("demo_mode", False)),
            "proof_fields": ["transaction_signature", "wallet_address", "level_session_id"],
            "verification_focus": [
                "transaction_exists",
                "transaction_succeeded",
                "wallet_signed",
                "required_accounts_included",
                "session_binding",
                "replay_protection",
            ],
        },
    }


def _build_level_2_challenge(
    level: Level,
    level_session_id: str,
    wallet_address: str,
    execution: dict[str, Any],
) -> dict[str, Any]:
    network = str(execution.get("network", "devnet"))
    program_id = str(execution.get("program_id", _pubkey(level_session_id, "program")))
    commander_registry_pda = _pubkey(level_session_id, wallet_address, "commander_registry_pda")
    trusted_commander_pda = _pubkey(level_session_id, wallet_address, "trusted_commander_pda")
    hijacked_commander_pda = _pubkey(level_session_id, wallet_address, "hijacked_commander_pda")
    authority_record_pda = _pubkey(level_session_id, wallet_address, "authority_record_pda")
    static_seed_pda = _pubkey("solbreach", level.slug, "static-commander")
    required_accounts = [
        program_id,
        commander_registry_pda,
        trusted_commander_pda,
        hijacked_commander_pda,
        authority_record_pda,
        static_seed_pda,
        wallet_address,
    ]
    return {
        "network": network,
        "level_session_id": level_session_id,
        "wallet_address": wallet_address,
        "program_id": program_id,
        "commander_registry_pda": commander_registry_pda,
        "trusted_commander_pda": trusted_commander_pda,
        "hijacked_commander_pda": hijacked_commander_pda,
        "authority_record_pda": authority_record_pda,
        "static_seed_pda": static_seed_pda,
        "expected_commander_after_hijack": wallet_address,
        "required_accounts": required_accounts,
        "required_pdas": [
            {
                "label": "commander_registry_pda",
                "address": commander_registry_pda,
                "seeds": ["solbreach", level.slug, level_session_id, "registry"],
            },
            {
                "label": "static_seed_pda",
                "address": static_seed_pda,
                "seeds": ["solbreach", level.slug, "static-commander"],
            },
        ],
        "exploit_parameters": {
            "vulnerability": "static_pda_commander_hijack",
            "mode": str(execution.get("mode", "wallet_signed_demo_transaction")),
            "demo_mode": bool(execution.get("demo_mode", False)),
            "attack_goal": "replace the trusted commander PDA path with the wallet-bound commander",
            "proof_fields": ["transaction_signature", "wallet_address", "level_session_id"],
            "verification_focus": [
                "transaction_exists",
                "transaction_succeeded",
                "wallet_signed",
                "required_accounts_included",
                "pda_commander_hijack_accounts",
                "session_binding",
                "replay_protection",
            ],
        },
    }


def _build_level_3_challenge(
    level: Level,
    level_session_id: str,
    wallet_address: str,
    execution: dict[str, Any],
) -> dict[str, Any]:
    network = str(execution.get("network", "devnet"))
    program_id = str(execution.get("program_id", _pubkey(level_session_id, "program")))
    guild_authority_pda = _pubkey(level_session_id, wallet_address, "guild_authority_pda")
    level3_state_pda = _pubkey(level_session_id, wallet_address, "level3_state_pda")
    bounty_vault_pda = _pubkey(level_session_id, wallet_address, "bounty_vault_pda")
    trusted_cpi_program = _pubkey("solbreach", level.slug, "trusted_cpi_program")
    attacker_cpi_program = _pubkey(level_session_id, wallet_address, "attacker_cpi_program")
    player_reward_account = _pubkey(level_session_id, wallet_address, "player_reward_account")
    authority_record_pda = _pubkey(level_session_id, wallet_address, "authority_record_pda")
    required_accounts = [
        wallet_address,
        guild_authority_pda,
        level3_state_pda,
        bounty_vault_pda,
        trusted_cpi_program,
        attacker_cpi_program,
        player_reward_account,
        authority_record_pda,
    ]
    return {
        "network": network,
        "level_session_id": level_session_id,
        "wallet_address": wallet_address,
        "program_id": program_id,
        "guild_authority_pda": guild_authority_pda,
        "level3_state_pda": level3_state_pda,
        "bounty_vault_pda": bounty_vault_pda,
        "trusted_cpi_program": trusted_cpi_program,
        "attacker_cpi_program": attacker_cpi_program,
        "player_reward_account": player_reward_account,
        "authority_record_pda": authority_record_pda,
        "required_accounts": required_accounts,
        "required_pdas": [
            {
                "label": "guild_authority_pda",
                "address": guild_authority_pda,
                "seeds": ["solbreach", level.slug, level_session_id, "guild-authority"],
            },
            {
                "label": "level3_state_pda",
                "address": level3_state_pda,
                "seeds": ["solbreach", level.slug, level_session_id, "state"],
            },
            {
                "label": "bounty_vault_pda",
                "address": bounty_vault_pda,
                "seeds": ["solbreach", level.slug, level_session_id, "bounty-vault"],
            },
        ],
        "exploit_parameters": {
            "vulnerability": "arbitrary_cpi_delegated_signer_abuse",
            "mode": str(execution.get("mode", "wallet_signed_demo_transaction")),
            "demo_mode": bool(execution.get("demo_mode", False)),
            "attack_goal": (
                "route delegated signer authority into attacker-controlled CPI and drain "
                "bounty credit to player reward account"
            ),
            "expected_sequence": ["target", "signer", "vault", "reward"],
            "proof_fields": ["transaction_signature", "wallet_address", "level_session_id"],
            "verification_focus": [
                "transaction_exists",
                "transaction_succeeded",
                "wallet_signed",
                "required_accounts_included",
                "delegated_cpi_account_set",
                "expected_sequence",
                "session_binding",
                "replay_protection",
            ],
        },
    }


def _build_level_4_challenge(
    level: Level,
    level_session_id: str,
    wallet_address: str,
    execution: dict[str, Any],
) -> dict[str, Any]:
    network = str(execution.get("network", "devnet"))
    program_id = str(execution.get("program_id", _pubkey(level_session_id, "program")))
    level4_state_pda = _pubkey(level_session_id, wallet_address, "level4_state_pda")
    market_pda = _pubkey(level_session_id, wallet_address, "market_pda")
    mismatched_market_pda = _pubkey(level_session_id, wallet_address, "mismatched_market_pda")
    position_pda = _pubkey(level_session_id, wallet_address, "position_pda")
    collateral_vault = _pubkey(level_session_id, wallet_address, "collateral_vault")
    mismatched_vault = _pubkey(level_session_id, wallet_address, "mismatched_vault")
    user_collateral = _pubkey(level_session_id, wallet_address, "user_collateral")
    expected_collateral_mint = _pubkey(level_session_id, wallet_address, "expected_mint")
    mismatched_collateral_mint = _pubkey(level_session_id, wallet_address, "mismatched_mint")
    required_accounts = [
        wallet_address,
        level4_state_pda,
        market_pda,
        mismatched_market_pda,
        position_pda,
        collateral_vault,
        mismatched_vault,
        user_collateral,
        expected_collateral_mint,
        mismatched_collateral_mint,
    ]
    return {
        "network": network,
        "level_session_id": level_session_id,
        "wallet_address": wallet_address,
        "program_id": program_id,
        "level4_state_pda": level4_state_pda,
        "market_pda": market_pda,
        "mismatched_market_pda": mismatched_market_pda,
        "position_pda": position_pda,
        "collateral_vault": collateral_vault,
        "mismatched_vault": mismatched_vault,
        "user_collateral": user_collateral,
        "expected_collateral_mint": expected_collateral_mint,
        "mismatched_collateral_mint": mismatched_collateral_mint,
        "required_accounts": required_accounts,
        "required_pdas": [
            {
                "label": "level4_state_pda",
                "address": level4_state_pda,
                "seeds": ["level_4", wallet_address],
            },
            {
                "label": "market_pda",
                "address": market_pda,
                "seeds": ["market", level_session_id],
            },
            {
                "label": "position_pda",
                "address": position_pda,
                "seeds": ["position", market_pda, wallet_address],
            },
        ],
        "exploit_parameters": {
            "vulnerability": "data_matching",
            "mode": "mismatched_account_relationship",
            "demo_mode": bool(execution.get("demo_mode", False)),
            "attack_goal": (
                "Route collateral using valid accounts whose stored relationships do not match"
            ),
            "expected_sequence": [
                "init_level_4",
                "route_collateral_with_mismatched_data",
                "verify_and_close_level_4",
            ],
            "proof_fields": [
                "market",
                "position.market",
                "market.collateral_vault",
                "provided_collateral_vault",
                "market.collateral_mint",
                "provided_token_mint",
            ],
            "verification_focus": [
                "valid account types",
                "mismatched stored fields",
                "state update accepted before data matching",
            ],
        },
    }


def _build_level_5_challenge(
    level: Level,
    level_session_id: str,
    wallet_address: str,
    execution: dict[str, Any],
) -> dict[str, Any]:
    network = str(execution.get("network", "devnet"))
    program_id = str(execution.get("program_id", _pubkey(level_session_id, "program")))
    order_id = hashlib.sha256(f"{level_session_id}:{wallet_address}:order".encode()).digest()[:8]
    order_id_hex = order_id.hex()
    level5_state_pda = _pubkey(level_session_id, wallet_address, "level5_state_pda")
    receipt_pda = _pubkey("receipt", order_id_hex)
    lifecycle_registry_pda = _pubkey("receipt_lifecycle", order_id_hex)
    required_accounts = [wallet_address, level5_state_pda, receipt_pda, lifecycle_registry_pda]
    return {
        "network": network,
        "level_session_id": level_session_id,
        "wallet_address": wallet_address,
        "program_id": program_id,
        "level5_state_pda": level5_state_pda,
        "receipt_pda": receipt_pda,
        "lifecycle_registry_pda": lifecycle_registry_pda,
        "order_id": order_id_hex,
        "expected_status_before": "Archived",
        "expected_status_after": "Open",
        "required_accounts": required_accounts,
        "required_pdas": [
            {
                "label": "level5_state_pda",
                "address": level5_state_pda,
                "seeds": ["level_5", wallet_address],
            },
            {
                "label": "receipt_pda",
                "address": receipt_pda,
                "seeds": ["receipt", order_id_hex],
            },
            {
                "label": "lifecycle_registry_pda",
                "address": lifecycle_registry_pda,
                "seeds": ["receipt_lifecycle", order_id_hex],
            },
        ],
        "exploit_parameters": {
            "vulnerability": "address_reuse",
            "mechanism": "pda_lifecycle",
            "mode": "stale_receipt_address_reuse",
            "demo_mode": bool(execution.get("demo_mode", False)),
            "attack_goal": "Reuse a stale PDA address and make it active again",
            "expected_sequence": [
                "init_level_5",
                "archive_receipt",
                "reopen_receipt",
                "verify_and_close_level_5",
            ],
            "proof_fields": [
                "receipt_pda",
                "order_id",
                "previous_status",
                "final_status",
                "generation",
                "address_reused",
            ],
            "verification_focus": [
                "same PDA address",
                "closed or archived lifecycle",
                "active state after address reuse",
            ],
        },
    }


def _pubkey(*parts: str) -> str:
    digest = hashlib.sha256(":".join(parts).encode("utf-8")).digest()
    return _base58_encode(digest)


def _base58_encode(raw: bytes) -> str:
    number = int.from_bytes(raw, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = BASE58_ALPHABET[remainder] + encoded
    padding = len(raw) - len(raw.lstrip(b"\0"))
    return ("1" * padding) + (encoded or "1")
