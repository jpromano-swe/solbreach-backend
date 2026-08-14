from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BreachRoom:
    id: str
    slug: str
    title: str
    display_name: str
    repository_url: str
    install_url: str
    audit_command: str
    summary: str
    contest_details: list[str]
    scope: list[str]
    known_issue_summary: list[str]
    xp_reward: int


BREACH_ROOM_1 = BreachRoom(
    id="breach-room-1",
    slug="breach-room-1",
    title="Vault Ledger",
    display_name="Breach Room 1: Vault Ledger",
    repository_url="https://github.com/jpromano-swe/solbreach-breachrooms",
    install_url="https://github.com/solanabr/auditor-skill",
    audit_command="/auditor:audit-cycle",
    summary=(
        "Audit the first backend-owned Breach Room challenge and submit a structured "
        "vulnerability report for review."
    ),
    contest_details=[
        "Review the Rust/Anchor challenge repository as a security reviewer.",
        "Submit one vulnerability report per finding.",
        "Submissions are stored in SolBreach and mirrored to a review PR.",
    ],
    scope=[
        "breach-room-1",
        "Rust and Anchor source files included in the room repository",
        "Tests and reproduction notes relevant to Vault Ledger behavior",
    ],
    known_issue_summary=[
        "Known issue details are hidden until judging.",
        "Do not rely on frontend-provided known issue answers for scoring.",
    ],
    xp_reward=500,
)

BREACH_ROOMS = [BREACH_ROOM_1]
BREACH_ROOM_BY_ID = {room.id: room for room in BREACH_ROOMS}
