from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ResearchLabSessionStatus(StrEnum):
    PROVISIONING = "provisioning"
    ACTIVE = "active"
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


TREASURY_MIRAGE_MANIFEST = ResearchLabManifest(
    id="rl-001",
    version="1.0.0",
    slug="treasury-mirage",
    lab_code="RL1",
    title="Treasury Mirage",
    difficulty="intermediate",
    estimated_time="45-75 minutes",
    xp_reward=250,
    status="active",
    summary=(
        "A small treasury-backed collateral vault reports unauthorized withdrawals. "
        "Inspect the protocol path and prove whether attacker-controlled account inputs "
        "can create illegitimate credit."
    ),
    scenario_briefing=(
        "The treasury team accepts collateral before allowing withdrawals from a protected "
        "vault. A withdrawal occurred without approved collateral entering the system. Your "
        "task is to inspect the visible program logic, review sandbox accounts, execute a "
        "controlled exploit attempt, and prove impact from runtime state."
    ),
    objective=(
        "Prove that a counterfeit collateral account can be credited and used to withdraw "
        "legitimate treasury value in the sandbox."
    ),
    allowed_files=["programs/treasury_mirage/src/lib.rs"],
    entry_file="programs/treasury_mirage/src/lib.rs",
    test_command="",
    template_ref="research-labs/treasury-mirage@v1",
    objective_ref="RL1_UNAUTHORIZED_TREASURY_WITHDRAWAL",
    visible_account_refs=[
        "treasury_vault",
        "accepted_collateral_mint",
        "counterfeit_collateral_mint",
        "attacker_collateral_account",
        "attacker_position",
        "attacker_reward_account",
    ],
    objectives=[
        "Inspect the collateral deposit and withdrawal behavior",
        "Compare approved and attacker-controlled collateral accounts",
        "Submit an exploit attempt in the sandbox",
        "Verify unauthorized treasury value movement",
    ],
    hints=[
        ResearchLabHint(
            id="account-substitution",
            title="Hint 1",
            body=(
                "Focus on whether the deposit path proves the submitted collateral account "
                "belongs to the accepted mint."
            ),
        ),
        ResearchLabHint(
            id="credit-boundary",
            title="Hint 2",
            body=(
                "The withdrawal path trusts position credit. Determine whether that credit can "
                "be produced from unapproved collateral."
            ),
        ),
    ],
)


RESEARCH_LABS = [TREASURY_MIRAGE_MANIFEST]
