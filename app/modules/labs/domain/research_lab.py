from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ResearchLabSessionStatus(StrEnum):
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    RUNNING = "running"
    VERIFIED = "verified"
    COMPLETED = "completed"
    DIRTY = "dirty"
    RUNNING_TESTS = "running_tests"
    PASSED = "passed"
    FAILED = "failed"
    EXPIRED = "expired"
    DESTROYED = "destroyed"
    ERROR = "error"


class ResearchLabTestRunStatus(StrEnum):
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    ERROR = "error"


class ResearchLabReportStatus(StrEnum):
    LOCKED = "locked"
    DRAFT = "draft"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    RETRY = "retry"


@dataclass(frozen=True, slots=True)
class ResearchLabHint:
    id: str
    title: str
    body: str


@dataclass(frozen=True, slots=True)
class ResearchLabManifest:
    id: str
    version: str
    slug: str
    aliases: list[str]
    lab_code: str
    title: str
    difficulty: str
    estimated_time: str
    xp_reward: int
    status: str
    summary: str
    scenario_briefing: str
    objective: str
    allowed_files: list[str]
    entry_file: str
    test_command: str
    template_ref: str
    objective_ref: str
    visible_account_refs: list[str]
    objectives: list[str]
    hints: list[ResearchLabHint] = field(default_factory=list)

    def learner_safe(self, *, include_details: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "version": self.version,
            "slug": self.slug,
            "lab_code": self.lab_code,
            "title": self.title,
            "difficulty": self.difficulty,
            "estimated_time": self.estimated_time,
            "xp_reward": self.xp_reward,
            "status": self.status,
            "summary": self.summary,
            "scenario_briefing": self.scenario_briefing,
            "objectives": self.objectives,
            "visible_account_refs": self.visible_account_refs,
            "hints_enabled": bool(self.hints),
        }
        if include_details:
            data.update(
                {
                    "objective": self.objective,
                    "allowed_files": self.allowed_files,
                    "entry_file": self.entry_file,
                    "hints": [
                        {"id": hint.id, "title": hint.title, "body": hint.body}
                        for hint in self.hints
                    ],
                }
            )
        return data


RL1_ACCOUNT_SUBSTITUTION_MANIFEST = ResearchLabManifest(
    id="rl1-account-substitution",
    version="1.0.0",
    slug="account-substitution",
    aliases=["rl-001"],
    lab_code="RL1",
    title="Account Substitution",
    difficulty="intermediate",
    estimated_time="45-75 minutes",
    xp_reward=250,
    status="active",
    summary=(
        "Inspect a vault-style collateral flow and prove whether non-canonical account "
        "relationships can mint illegitimate protocol credit and drain treasury value."
    ),
    scenario_briefing=(
        "The protocol credits positions when collateral is deposited, then allows value to be "
        "withdrawn from a protected treasury. Your job is to inspect the visible program logic, "
        "submit controlled exploit actions, review the resulting evidence, and prove whether a "
        "missing account binding allows illegitimate treasury withdrawal."
    ),
    objective=(
        "Prove that missing account binding lets a caller substitute non-canonical collateral "
        "and vault relationships, receive illegitimate credit, then withdraw real protocol "
        "treasury value."
    ),
    allowed_files=["programs/account_substitution/src/lib.rs"],
    entry_file="programs/account_substitution/src/lib.rs",
    test_command="",
    template_ref="research-labs/account-substitution@v1",
    objective_ref="RL1_ACCOUNT_SUBSTITUTION_IMPACT",
    visible_account_refs=[
        "treasury_vault",
        "official_mint_account",
        "counterfeit_mint_account",
        "attacker_collateral_account",
        "official_collateral_account",
        "counterfeit_vault_account",
        "official_vault_account",
        "position",
        "attacker_reward_account",
    ],
    objectives=[
        "Inspect the collateral and treasury account relationships",
        "Execute controlled exploit actions in the sandbox",
        "Review transaction and account evidence",
        "Prove unauthorized treasury withdrawal from invalid credit",
    ],
    hints=[
        ResearchLabHint(
            id="account-substitution",
            title="Hint 1",
            body=(
                "Focus on whether the deposit path binds the submitted collateral source and "
                "vault destination to an approved relationship."
            ),
        ),
        ResearchLabHint(
            id="credit-boundary",
            title="Hint 2",
            body=(
                "The withdrawal path trusts stored position credit. Determine whether invalid "
                "credit can be created before treasury value moves."
            ),
        ),
    ],
)


RL2_YIELD_HIJACK_MANIFEST = ResearchLabManifest(
    id="rl2-yield-hijack",
    version="1.0.0",
    slug="yield-hijack",
    aliases=["rl-002", "yield-hijack"],
    lab_code="RL2",
    title="Yield Hijack",
    difficulty="intermediate",
    estimated_time="45-75 minutes",
    xp_reward=300,
    status="active",
    summary=(
        "Inspect a high-APY staking pool and prove how a staking-position PDA scoped only "
        "to the pool lets one participant inherit another user's rewards."
    ),
    scenario_briefing=(
        "An existing participant has already staked into a promotional yield pool and accrued rewards. "
        "Your job is to inspect the staking position derivation, execute controlled staking "
        "and reward-claim actions, and prove whether the position identity is shared across users."
    ),
    objective=(
        "Prove that a staking-position PDA derived from only the pool address lets another user "
        "overwrite the position owner, preserve the existing principal and pending rewards, then "
        "claim those rewards."
    ),
    allowed_files=["programs/yield_hijack/src/lib.rs"],
    entry_file="programs/yield_hijack/src/lib.rs",
    test_command="",
    template_ref="research-labs/yield-hijack@v1",
    objective_ref="RL2_STATIC_PDA_REWARD_HIJACK_IMPACT",
    visible_account_refs=[
        "pool_config",
        "pool_authority",
        "stake_mint",
        "reward_mint",
        "stake_vault",
        "reward_vault",
        "stake_position",
        "user_stake_account",
        "user_reward_account",
        "existing_staker_stake_account",
        "existing_staker_reward_account",
    ],
    objectives=[
        "Inspect staking position PDA derivation",
        "Attempt a reward claim before ownership takeover",
        "Stake from your wallet and observe position ownership",
        "Claim pre-existing rewards and prove reward-vault impact",
    ],
    hints=[
        ResearchLabHint(
            id="position-seeds",
            title="Hint 1",
            body="Compare which seeds are used for the existing staker and your staking position.",
        ),
        ResearchLabHint(
            id="reward-claim-owner",
            title="Hint 2",
            body="The reward claim checks the stored position owner, not the original depositor.",
        ),
    ],
)


RL3_ARBITRARY_CPI_MANIFEST = ResearchLabManifest(
    id="rl3-arbitrary-cpi",
    version="1.0.0",
    slug="arbitrary-cpi",
    aliases=["rl-003", "arbitrary-cpi"],
    lab_code="RL3",
    title="Arbitrary CPI",
    difficulty="advanced",
    estimated_time="60-90 minutes",
    xp_reward=350,
    status="active",
    summary=(
        "Inspect a TaskBounty payout flow and prove whether a caller-supplied CPI target "
        "can replace the approved payout router and drain escrowed task rewards."
    ),
    scenario_briefing=(
        "A bounty platform delegates payout execution after a worker completes a task. "
        "Your job is to inspect the public program interface, build and deploy a controlled "
        "session-scoped attacker program inside the SolBreach sandbox, then prove whether "
        "the vulnerable delegated payout instruction accepts that attacker program as the CPI target."
    ),
    objective=(
        "Prove that arbitrary CPI target selection lets a caller replace the approved payout "
        "router with a session-scoped attacker program and drain task escrow into the attacker "
        "reward account."
    ),
    allowed_files=["programs/task_bounty/src/lib.rs"],
    entry_file="programs/task_bounty/src/lib.rs",
    test_command="",
    template_ref="research-labs/arbitrary-cpi@v1",
    objective_ref="RL3_ARBITRARY_CPI_BOUNTY_DRAIN_IMPACT",
    visible_account_refs=[
        "bounty_config",
        "bounty_authority",
        "bounty_vault",
        "task_record",
        "task_escrow",
        "official_payout_router",
        "approved_worker_account",
        "attacker_reward_account",
        "attacker_program_buffer",
    ],
    objectives=[
        "Inspect the delegated payout program interface",
        "Build a controlled attacker CPI program inside the sandbox",
        "Deploy the session-scoped attacker program",
        "Execute delegated payout with the attacker CPI target and prove escrow impact",
    ],
    hints=[
        ResearchLabHint(
            id="public-idl",
            title="Hint 1",
            body="Find the delegated payout instruction through the public IDL, not through the reward candidate data.",
        ),
        ResearchLabHint(
            id="cpi-target",
            title="Hint 2",
            body="Focus on whether the payout instruction binds the CPI target to the approved router.",
        ),
    ],
)


RESEARCH_LABS = [
    RL1_ACCOUNT_SUBSTITUTION_MANIFEST,
    RL2_YIELD_HIJACK_MANIFEST,
    RL3_ARBITRARY_CPI_MANIFEST,
]
