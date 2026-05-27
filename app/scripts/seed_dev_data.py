import asyncio
import os
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import AsyncSessionLocal
from app.core.security.password import PasswordHasher
from app.modules.levels.domain.entities.level import LevelStage
from app.modules.levels.infrastructure.database.models import LevelModel
from app.modules.users.domain.entities.user import UserRole
from app.modules.users.infrastructure.database.models import UserModel
from app.modules.vulnerabilities.infrastructure.database.models import VulnerabilityModel

VULNERABILITIES = [
    {
        "slug": "pda_state_validation",
        "title": "PDA State Validation",
        "category": "pda_misuse",
        "difficulty": "easy",
        "description": "Validate a deterministic PDA state transition after exploit success.",
        "tags": ["pda", "state", "beginner"],
    },
    {
        "slug": "fake_mint",
        "title": "Fake Mint",
        "category": "token_validation",
        "difficulty": "easy",
        "description": "Detect exploit success through deterministic token balance outcomes.",
        "tags": ["spl-token", "mint", "balance"],
    },
    {
        "slug": "authority_spoofing",
        "title": "Authority Spoofing",
        "category": "authority",
        "difficulty": "medium",
        "description": "Validate authority transitions caused by a spoofed-authority exploit.",
        "tags": ["authority", "ownership", "spoofing"],
    },
    {
        "slug": "unchecked_cpi",
        "title": "Unchecked CPI",
        "category": "cpi",
        "difficulty": "medium",
        "description": "Validate transaction and account outcomes from an unchecked CPI exploit.",
        "tags": ["cpi", "transaction", "accounts"],
    },
    {
        "slug": "advanced_bounty_drainer",
        "title": "Advanced Bounty Drainer",
        "category": "cpi",
        "difficulty": "hard",
        "description": "Placeholder vulnerability for the post-Level 3 continuation path.",
        "tags": ["cpi", "advanced", "placeholder"],
    },
]


LEVELS = [
    {
        "slug": "level-1-fake-mint",
        "title": "Level 1: The Illusionist",
        "description": (
            "Exploit a fake mint path where counterfeit token accounts and vault substitution "
            "hide the attacker-controlled asset behind a trusted-looking flow."
        ),
        "order": 1,
        "vulnerability_slug": "fake_mint",
        "vulnerability_category": "token_validation",
        "difficulty": "easy",
        "xp_reward": 100,
        "objectives": [
            "Identify the missing mint authenticity check.",
            "Prepare the deterministic devnet challenge state.",
            "Execute the wallet-signed exploit transaction.",
            "Submit the transaction signature for deterministic verification.",
        ],
        "instructions": (
            "Connect a wallet, start the level, run setup, sign the exploit transaction on "
            "devnet, and submit the resulting transaction signature. The backend prepares "
            "challenge metadata and verifies outcomes; it never signs or submits for you."
        ),
        "verification_requirements": [
            "Transaction must exist and succeed on Solana devnet.",
            "Connected wallet must be a signer.",
            "Transaction must include the session-bound challenge accounts.",
            "Level session and wallet must match the setup context.",
            "Transaction signature must not have been used before.",
        ],
        "resources": [{"label": "Starter repo", "url": "https://example.com/solbreach/level-1"}],
        "verification_config": {
            "checks": [
                {"type": "session_binding"},
                {"type": "replay_protection"},
                {
                    "type": "transaction_signature",
                    "require_success": True,
                },
                {
                    "type": "solana_transaction",
                    "require_success": True,
                    "require_wallet_signer": True,
                    "require_challenge_accounts": True,
                },
            ]
        },
        "example_proof": {
            "transaction_signature": "demo-signature-level-1-abcdef",
            "transaction_succeeded": True,
        },
        "demo_wallet": "DemoWallet111111111111111111111111111111111",
        "demo_accounts": {
            "fake_mint": "FakeMint11111111111111111111111111111111111",
            "vault": "Vault111111111111111111111111111111111111",
        },
        "execution": {
            "enabled": True,
            "mode": "wallet_signed_demo_transaction",
            "network": "devnet",
            "program_id": "11111111111111111111111111111111",
            "demo_mode": True,
        },
    },
    {
        "slug": "level-2-authority-spoofing",
        "title": "Level 2: Static PDA Commander",
        "description": (
            "Exploit an authority path that trusts a static commander PDA and prove the "
            "wallet-signed transaction includes the intended hijack accounts."
        ),
        "order": 2,
        "vulnerability_slug": "authority_spoofing",
        "vulnerability_category": "authority",
        "difficulty": "medium",
        "xp_reward": 250,
        "objectives": [
            "Inspect the static PDA commander trust path.",
            "Prepare the deterministic commander hijack challenge state.",
            "Execute the wallet-signed devnet proof transaction.",
            "Submit the transaction signature for deterministic verification.",
        ],
        "instructions": (
            "Start Level 2, run setup with the connected wallet, build a devnet transaction "
            "that includes every commander challenge account, sign with the wallet, and submit "
            "the resulting signature. The backend verifies the transaction and session context; "
            "it does not sign or submit anything for you."
        ),
        "verification_requirements": [
            "Transaction must exist and succeed on Solana devnet.",
            "Connected wallet must be a signer.",
            "Transaction must include the session-bound commander challenge accounts.",
            "Level session and wallet must match the setup context.",
            "Transaction signature must not have been used before.",
        ],
        "resources": [{"label": "Starter repo", "url": "https://example.com/solbreach/level-2"}],
        "verification_config": {
            "checks": [
                {"type": "session_binding"},
                {"type": "replay_protection"},
                {
                    "type": "transaction_signature",
                    "require_success": True,
                },
                {
                    "type": "solana_transaction",
                    "require_success": True,
                    "require_wallet_signer": True,
                    "require_challenge_accounts": True,
                },
                {
                    "type": "pda_commander_hijack",
                    "required_account_labels": [
                        "commander_registry_pda",
                        "trusted_commander_pda",
                        "hijacked_commander_pda",
                        "authority_record_pda",
                        "wallet_address",
                    ],
                },
            ]
        },
        "example_proof": {
            "transaction_signature": "demo-signature-level-2-abcdef",
            "transaction_succeeded": True,
        },
        "demo_wallet": "DemoWallet111111111111111111111111111111111",
        "demo_accounts": {
            "target": "AuthorityTarget111111111111111111111111111",
        },
        "execution": {
            "enabled": True,
            "mode": "wallet_signed_demo_transaction",
            "challenge_type": "static_pda_commander_hijack",
            "network": "devnet",
            "program_id": "11111111111111111111111111111111",
            "demo_mode": True,
        },
    },
    {
        "slug": "level-3-unchecked-cpi",
        "title": "Level 3: The Trojan Horse",
        "description": (
            "Exploit an arbitrary CPI target path where delegated signer authority is "
            "forwarded into an attacker-controlled CPI target."
        ),
        "order": 3,
        "vulnerability_slug": "unchecked_cpi",
        "vulnerability_category": "cpi",
        "difficulty": "medium",
        "xp_reward": 300,
        "objectives": [
            "Identify the attacker-controlled CPI target.",
            "Trace the forwarded guild signer authority.",
            "Map the bounty vault and player reward account path.",
            "Submit a wallet-signed devnet proof transaction with the Level 3 account set.",
        ],
        "instructions": (
            "Use the local observe/manipulate flow to reconstruct the delegated-CPI exploit "
            "sequence, then run setup, sign a deterministic devnet transaction that includes "
            "the Level 3 exploit accounts, and submit the resulting signature."
        ),
        "verification_requirements": [
            "Transaction must exist and succeed on Solana devnet.",
            "Connected wallet must be a signer.",
            "Transaction must include the Level 3 delegated-CPI challenge accounts.",
            "Level session and wallet must match the setup context.",
            "Transaction signature must not have been used before.",
        ],
        "resources": [{"label": "Starter repo", "url": "https://example.com/solbreach/level-3"}],
        "verification_config": {
            "checks": [
                {"type": "session_binding"},
                {"type": "replay_protection"},
                {
                    "type": "transaction_signature",
                    "require_success": True,
                },
                {
                    "type": "solana_transaction",
                    "require_success": True,
                    "require_wallet_signer": True,
                    "require_challenge_accounts": True,
                },
                {
                    "type": "delegated_cpi_exploit",
                    "expected_sequence": ["target", "signer", "vault", "reward"],
                    "required_account_labels": [
                        "wallet_address",
                        "guild_authority_pda",
                        "level3_state_pda",
                        "bounty_vault_pda",
                        "trusted_cpi_program",
                        "attacker_cpi_program",
                        "player_reward_account",
                        "authority_record_pda",
                    ],
                },
            ]
        },
        "example_proof": {
            "transaction_signature": "demo-signature-level-3-abcdef",
            "transaction_succeeded": True,
        },
        "demo_wallet": "DemoWallet111111111111111111111111111111111",
        "demo_accounts": {
            "target": "UncheckedCpiTarget111111111111111111111111",
        },
        "execution": {
            "enabled": True,
            "mode": "wallet_signed_demo_transaction",
            "challenge_type": "arbitrary_cpi_delegated_signer_abuse",
            "network": "devnet",
            "program_id": "11111111111111111111111111111111",
            "demo_mode": True,
        },
    },
    {
        "slug": "level-4-advanced-bounty-drainer",
        "title": "Level 4: Advanced Bounty Drainer",
        "description": "Post-demo continuation level placeholder unlocked after Level 3.",
        "order": 4,
        "vulnerability_slug": "advanced_bounty_drainer",
        "vulnerability_category": "cpi",
        "difficulty": "hard",
        "xp_reward": 500,
        "objectives": [
            "Continue the advanced CPI exploitation path.",
        ],
        "instructions": "This level is reserved for the next playable slice.",
        "verification_requirements": [
            "Coming soon.",
        ],
        "resources": [],
        "verification_config": {"checks": []},
        "example_proof": {},
        "demo_wallet": "DemoWallet111111111111111111111111111111111",
        "demo_accounts": {},
        "execution": {"enabled": False},
    },
]


def stable_id(slug: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"solbreach:{slug}"))


async def seed_development_data(session: AsyncSession) -> None:
    await seed_admin_user(session)
    vulnerability_ids: dict[str, str] = {}
    for item in VULNERABILITIES:
        existing = await session.scalar(
            select(VulnerabilityModel).where(VulnerabilityModel.slug == item["slug"])
        )
        if existing is None:
            existing = VulnerabilityModel(
                id=stable_id(str(item["slug"])),
                slug=item["slug"],
                title=item["title"],
                category=item["category"],
                difficulty=item["difficulty"],
                description=item["description"],
                tags=item["tags"],
            )
            session.add(existing)
            await session.flush()
        vulnerability_ids[existing.slug] = existing.id

    for item in LEVELS:
        existing = await session.scalar(select(LevelModel).where(LevelModel.slug == item["slug"]))
        values = {
            "id": stable_id(str(item["slug"])),
            "slug": item["slug"],
            "title": item["title"],
            "description": item["description"],
            "order": item["order"],
            "stage": LevelStage.VULNERABILITIES.value,
            "vulnerability_id": vulnerability_ids[str(item["vulnerability_slug"])],
            "vulnerability_category": item["vulnerability_category"],
            "difficulty": item["difficulty"],
            "objectives": item["objectives"],
            "instructions": item["instructions"],
            "verification_requirements": item["verification_requirements"],
            "repository_url": None,
            "resources": item["resources"],
            "verification_config": item["verification_config"],
            "deployment_info": {
                "mode": "deterministic_proof",
                "example_proof": item["example_proof"],
                "demo_wallet": item["demo_wallet"],
                "demo_accounts": item["demo_accounts"],
                "execution": item.get("execution", {"enabled": False}),
            },
            "xp_reward": item["xp_reward"],
            "is_active": True,
        }
        if existing is None:
            session.add(
                LevelModel(
                    **values,
                )
            )
        else:
            for key, value in values.items():
                if key != "id":
                    setattr(existing, key, value)
    await session.commit()


async def seed_admin_user(session: AsyncSession) -> None:
    password = os.getenv("SOLBREACH_ADMIN_PASSWORD")
    if not password:
        return

    username = os.getenv("SOLBREACH_ADMIN_USERNAME", "solbreach_admin")
    email = os.getenv("SOLBREACH_ADMIN_EMAIL", "admin@solbreach.app")
    existing = await session.scalar(select(UserModel).where(UserModel.email == email))
    password_hash = PasswordHasher().hash(password)

    if existing is None:
        session.add(
            UserModel(
                id=stable_id(f"user:{email}"),
                username=username,
                email=email,
                hashed_password=password_hash,
                role=UserRole.ADMIN.value,
                wallet_address=None,
                bio=None,
                avatar=None,
                xp=0,
                reputation_score=0,
                completed_levels=0,
            )
        )
        await session.flush()
        return

    existing.username = username
    existing.hashed_password = password_hash
    existing.role = UserRole.ADMIN.value
    existing.deleted_at = None
    await session.flush()


async def main() -> None:
    async with AsyncSessionLocal() as session:
        await seed_development_data(session)


if __name__ == "__main__":
    asyncio.run(main())
