from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class SandboxTerminalEvent:
    stream: str
    line: str


@dataclass(slots=True)
class SandboxTestResult:
    id: str
    label: str
    passed: bool
    details: str | None = None


@dataclass(slots=True)
class SandboxTestRunResult:
    status: str
    exit_code: int | None
    terminal_events: list[SandboxTerminalEvent] = field(default_factory=list)
    results: list[SandboxTestResult] = field(default_factory=list)


@dataclass(slots=True)
class SandboxAccountSummary:
    ref: str
    label: str
    owner: str
    lamports: int
    data: dict


@dataclass(slots=True)
class SandboxAccountSnapshot:
    ref: str
    label: str
    owner: str
    lamports: int
    data: dict


@dataclass(slots=True)
class SandboxExplorerSnapshot:
    session_id: str
    network: dict
    program: dict
    accounts: list[dict]
    reward_candidates: list[dict] = field(default_factory=list)
    total_rewards_paid: int = 0
    enabled: bool = True
    reason: str | None = None


@dataclass(slots=True)
class SandboxTransactionResult:
    transaction_ref: str
    instruction_type: str
    execution_status: str
    logs: list[str] = field(default_factory=list)
    account_deltas: list[dict] = field(default_factory=list)
    protocol_state: dict = field(default_factory=dict)
    user_facing_evidence: list[Any] = field(default_factory=list)


def resolve_lab_template_ref(template_ref: str) -> str:
    if template_ref == "research-labs/account-substitution@v1":
        return "research-labs/treasury-mirage@v1"
    return template_ref


def resolve_lab_file_path(path: str) -> str:
    if path == "programs/account_substitution/src/lib.rs":
        return "programs/treasury_mirage/src/lib.rs"
    return path


@dataclass(slots=True)
class SandboxVerificationResult:
    objective_ref: str
    passed: bool
    evidence: dict
    verified_evidence_refs: list[str] = field(default_factory=list)
    failure_reason: str | None = None
    user_facing_evidence: list[Any] = field(default_factory=list)


class SandboxRuntime(Protocol):
    async def create_session(self, session_id: str, template_ref: str) -> str: ...

    async def hydrate_template(self, session_id: str, template_ref: str) -> None: ...

    async def read_file(self, session_id: str, path: str) -> str: ...

    async def patch_file(self, session_id: str, path: str, content: str) -> None: ...

    async def run_tests(
        self, session_id: str, command: str, timeout_seconds: int
    ) -> SandboxTestRunResult: ...

    async def reset_session(self, session_id: str, template_ref: str) -> None: ...

    async def destroy_session(self, session_id: str) -> None: ...

    async def get_visible_accounts(self, session_id: str) -> list[SandboxAccountSummary]: ...

    async def get_account_state(
        self, session_id: str, account_ref: str
    ) -> SandboxAccountSnapshot: ...

    async def get_explorer_snapshot(self, session_id: str) -> SandboxExplorerSnapshot: ...

    async def submit_transaction(
        self, session_id: str, action_type: str, parameters: dict
    ) -> SandboxTransactionResult: ...

    async def get_transaction_logs(self, session_id: str, transaction_ref: str) -> list[str]: ...

    async def verify_objective(
        self, session_id: str, objective_ref: str
    ) -> SandboxVerificationResult: ...
