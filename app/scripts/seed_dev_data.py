import asyncio
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import AsyncSessionLocal
from app.modules.levels.domain.entities.level import LevelStage
from app.modules.levels.infrastructure.database.models import LevelModel
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
]


LEVELS = [
    {
        "slug": "level-1-fake-mint",
        "title": "Level 1: Fake Mint",
        "description": (
            "Exploit weak mint validation and prove the attacker received tokens from "
            "the protected vault."
        ),
        "order": 1,
        "vulnerability_slug": "fake_mint",
        "vulnerability_category": "token_validation",
        "difficulty": "easy",
        "xp_reward": 100,
        "objectives": [
            "Identify the missing mint authenticity check.",
            "Execute the exploit locally or on devnet.",
            "Submit deterministic token balance proof.",
        ],
        "instructions": (
            "Use the provided starter flow with the demo wallet. The backend will only "
            "verify the submitted deterministic outcome; it will not execute your code."
        ),
        "verification_requirements": [
            "A known successful demo transaction signature.",
            "attacker_token_delta must equal 1000.",
            "vault_delta must equal -1000.",
        ],
        "resources": [{"label": "Starter repo", "url": "https://example.com/solbreach/level-1"}],
        "verification_config": {
            "checks": [
                {
                    "type": "transaction_signature",
                    "require_success": True,
                    "expected_signature": "demo-signature-level-1-abcdef",
                },
                {
                    "type": "token_balance",
                    "expected": {"attacker_token_delta": 1000, "vault_delta": -1000},
                },
            ]
        },
        "example_proof": {
            "transaction_signature": "demo-signature-level-1-abcdef",
            "transaction_succeeded": True,
            "token_balances": {"attacker_token_delta": 1000, "vault_delta": -1000},
        },
        "demo_wallet": "DemoWallet111111111111111111111111111111111",
        "demo_accounts": {
            "fake_mint": "FakeMint11111111111111111111111111111111111",
            "vault": "Vault111111111111111111111111111111111111",
        },
    },
    {
        "slug": "level-2-authority-spoofing",
        "title": "Level 2: Authority Spoofing",
        "description": "Prove the expected authority transition occurred.",
        "order": 2,
        "vulnerability_slug": "authority_spoofing",
        "vulnerability_category": "authority",
        "difficulty": "medium",
        "xp_reward": 250,
        "objectives": [
            "Inspect the trusted authority path.",
            "Demonstrate the spoofed authority transition.",
        ],
        "instructions": "Exploit the authority check and submit the resulting authority state.",
        "verification_requirements": [
            "A successful transaction signature.",
            "new_authority must equal attacker.",
            "owner_changed must be true.",
        ],
        "resources": [{"label": "Starter repo", "url": "https://example.com/solbreach/level-2"}],
        "verification_config": {
            "checks": [
                {"type": "transaction_signature", "require_success": True},
                {
                    "type": "authority",
                    "expected": {"new_authority": "attacker", "owner_changed": True},
                },
            ]
        },
        "example_proof": {
            "transaction_signature": "demo-signature-level-2-abcdef",
            "transaction_succeeded": True,
            "authority": {"new_authority": "attacker", "owner_changed": True},
        },
        "demo_wallet": "DemoWallet111111111111111111111111111111111",
        "demo_accounts": {
            "target": "AuthorityTarget111111111111111111111111111",
        },
    },
    {
        "slug": "level-3-unchecked-cpi",
        "title": "Level 3: Unchecked CPI",
        "description": (
            "Prove the unchecked CPI produced the expected transaction and account outcome."
        ),
        "order": 3,
        "vulnerability_slug": "unchecked_cpi",
        "vulnerability_category": "cpi",
        "difficulty": "medium",
        "xp_reward": 250,
        "objectives": [
            "Trigger the unchecked CPI path.",
            "Prove the target account was modified.",
        ],
        "instructions": "Exploit the unchecked CPI path and submit transaction plus PDA proof.",
        "verification_requirements": [
            "A successful transaction signature.",
            "cpi_executed must be true.",
            "target_modified must be true.",
        ],
        "resources": [{"label": "Starter repo", "url": "https://example.com/solbreach/level-3"}],
        "verification_config": {
            "checks": [
                {"type": "transaction_signature", "require_success": True},
                {"type": "pda_state", "expected": {"cpi_executed": True, "target_modified": True}},
            ]
        },
        "example_proof": {
            "transaction_signature": "demo-signature-level-3-abcdef",
            "transaction_succeeded": True,
            "pda_state": {"cpi_executed": True, "target_modified": True},
        },
        "demo_wallet": "DemoWallet111111111111111111111111111111111",
        "demo_accounts": {
            "target": "UncheckedCpiTarget111111111111111111111111",
        },
    },
]


def stable_id(slug: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"solbreach:{slug}"))


async def seed_development_data(session: AsyncSession) -> None:
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


async def main() -> None:
    async with AsyncSessionLocal() as session:
        await seed_development_data(session)


if __name__ == "__main__":
    asyncio.run(main())
