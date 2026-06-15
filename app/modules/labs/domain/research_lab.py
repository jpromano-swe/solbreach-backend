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
    allowed_files=["programs/treasury_mirage/src/lib.rs"],
    entry_file="programs/treasury_mirage/src/lib.rs",
    test_command="",
    template_ref="research-labs/treasury-mirage@v1",
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


RESEARCH_LABS = [RL1_ACCOUNT_SUBSTITUTION_MANIFEST]
