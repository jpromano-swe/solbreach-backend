# SolBreach Research Labs Backend Handoff

## Objective

Build the first backend-backed Research Labs runtime for SolBreach.

V1 goal:

```txt
User edits a constrained Solana/Anchor code fragment
-> backend applies the patch inside an isolated sandbox
-> backend runs real SVM-backed tests
-> frontend receives terminal output, structured test results, and objective progress
```

This must be real SVM execution, not a simulated database update.

The browser should not execute Solana programs. The backend owns sandbox orchestration and test execution.

---

## Product Scope

### In Scope For V1

- Research Lab catalog.
- Research Lab 1 session creation.
- File template hydration.
- Allowed-file patching.
- Backend-executed test runs.
- Terminal output capture.
- Structured test results.
- Objective progress updates.
- Session reset and expiration.
- Backend-owned completion state.

### Out Of Scope For V1

- Breach Rooms.
- Partner rooms.
- Reviewer workflow.
- Public credential minting for Research Labs.
- Full validator-style RPC sessions.
- Arbitrary shell execution.
- Full deployment to devnet.
- Learner-provided custom scripts.
- Open-ended exploit submission.
- WebSocket streaming if polling is faster to ship.

Polling terminal output is acceptable for V1.

---

## Current Frontend State

The frontend already has a Research Labs UI prototype:

- Lab catalog.
- Vault Mirage workspace.
- Monaco editor.
- xterm terminal surface.
- File tree.
- Right-side lab status, objective, hints, account viewer, quick actions.
- Local mocked evaluator.

The frontend mock must be replaced with backend calls once these APIs exist.

The mock runner must never grant real lab completion or credentials.

---

## Research Lab 1 Decision

Use the current frontend lab direction:

```txt
RL-007: Vault Mirage
Theme: vault health-factor arithmetic bug
Task: repair unchecked collateral-health arithmetic
Runtime: backend sandbox with real SVM-backed tests
```

Important correction:

Some architecture notes describe Vault Mirage as a fake collateral / unauthorized withdrawal lab. Do not use that for Research Lab 1 V1. That overlaps too much with Level 1. Use the arithmetic health-factor version for the first lab.

---

## Research Lab 1 Manifest

Suggested manifest shape:

```json
{
  "id": "rl-007",
  "slug": "vault-mirage",
  "title": "Vault Mirage",
  "difficulty": "intermediate",
  "estimated_time": "2-4 hours",
  "xp_reward": 250,
  "status": "active",
  "summary": "A lending protocol reports suspicious vault health calculations. Review the deposit path and repair the arithmetic trust boundary.",
  "objective": "Identify and fix the arithmetic flaw that lets attacker-controlled oracle input distort collateral health.",
  "allowed_files": [
    "programs/vault_mirage/src/lib.rs"
  ],
  "entry_file": "programs/vault_mirage/src/lib.rs",
  "test_command": "anchor test --skip-deploy",
  "success_criteria": "Collateral value must use checked multiplication and checked division before the health comparison.",
  "template_ref": "research-labs/vault-mirage@v1",
  "objectives": [
    "Inspect the vault health calculation",
    "Identify the unchecked arithmetic boundary",
    "Patch the vulnerable code fragment",
    "Run the sandboxed lab tests"
  ],
  "hints": [
    {
      "id": "health-calculation",
      "title": "Hint 1",
      "body": "Focus on the line that multiplies deposited amount by oracle price before scaling."
    },
    {
      "id": "checked-arithmetic",
      "title": "Hint 2",
      "body": "The safe pattern should make overflow impossible before the health comparison executes."
    }
  ]
}
```

---

## Vulnerable Code Fragment

The initial vulnerable pattern should be similar to:

```rust
pub fn deposit(ctx: Context<Deposit>, amount: u64, oracle_price: u64) -> Result<()> {
    let vault = &mut ctx.accounts.vault;
    let user = &mut ctx.accounts.user;

    // Vulnerable: multiplication can overflow before scaling.
    let collateral_value = amount * oracle_price / ORACLE_SCALE;

    require!(
        collateral_value >= MIN_HEALTH_FACTOR,
        ErrorCode::InsufficientHealth
    );

    vault.total_deposits = vault
        .total_deposits
        .checked_add(amount)
        .ok_or(ErrorCode::MathOverflow)?;

    user.deposits = user
        .deposits
        .checked_add(amount)
        .ok_or(ErrorCode::MathOverflow)?;

    Ok(())
}
```

Expected learner fix should use checked arithmetic before the health comparison:

```rust
let collateral_value = amount
    .checked_mul(oracle_price)
    .ok_or(ErrorCode::MathOverflow)?
    .checked_div(ORACLE_SCALE)
    .ok_or(ErrorCode::MathOverflow)?;
```

The exact solution should not be exposed by public APIs.

---

## Runtime Requirement

Research Labs V1 must execute real Solana/SVM logic.

Recommended first implementation:

```txt
Backend sandbox
-> hydrate lab package
-> apply allowed file patch
-> run predefined command
-> tests use LiteSVM or Mollusk internally
-> collect terminal output and structured results
```

Recommended runtime options:

1. Fastest managed path: Modal Sandboxes.
2. Self-hosted later: Kubernetes jobs/pods with gVisor or GKE Sandbox.
3. Local development fallback: local process runtime behind the same interface.

Do not use browser-only WebContainers for this V1. They are not the right runtime for realistic Rust/Anchor/Solana execution.

---

## Runtime Interface

Create a runtime abstraction before coupling to Modal, Kubernetes, or local process execution.

Suggested Python protocol/interface:

```python
class SandboxRuntime:
    async def create_session(self, lab_definition, participant) -> SandboxSession:
        ...

    async def hydrate_template(self, session_id: str) -> None:
        ...

    async def patch_file(self, session_id: str, path: str, content: str) -> None:
        ...

    async def run_tests(self, session_id: str) -> TestRunResult:
        ...

    async def get_terminal_events(self, session_id: str, after_sequence: int | None = None):
        ...

    async def reset_session(self, session_id: str) -> None:
        ...

    async def destroy_session(self, session_id: str) -> None:
        ...
```

Possible adapters:

- `MockSandboxRuntime`: local/frontend development only, cannot complete real labs.
- `LocalProcessSandboxRuntime`: backend dev/test fallback.
- `ModalSandboxRuntime`: recommended V1 production runtime.
- `KubernetesGvisorRuntime`: later scale/isolation option.
- `SurfpoolRuntime`: later validator-style interactive sessions.

---

## Backend Module Placement

Use the existing backend modular monolith.

Do not create a separate backend service yet.

Extend:

```txt
app/modules/labs
```

Add:

```txt
app/modules/sandbox
```

Optional later:

```txt
app/modules/reports
app/modules/rooms
```

The current backend already has:

- `app/modules/labs`
- `app/modules/levels`
- `app/modules/progress`
- `app/modules/certifications`
- `app/modules/submissions`

That structure is enough for V1.

---

## Repository Strategy

Do not create a new backend repo for V1.

Use current backend repo:

```txt
solbreach_backend
```

Create a separate private lab content repo soon, once the first real lab package is defined:

```txt
solbreach-active-labs
```

That private repo should contain:

- active lab templates
- vulnerable Anchor programs
- hidden tests
- internal solutions
- seed fixtures
- verifier definitions
- variant banks

The public/frontend repo may contain UI and high-level lab metadata, but not hidden tests or active solutions.

---

## Data Model V1

The existing `labs` table can remain as public metadata, but Research Labs need session/test/file state.

Suggested tables:

### `research_lab_sessions`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `user_id` | UUID | Owner |
| `lab_id` | UUID/TEXT | Lab reference |
| `lab_slug` | TEXT | Example: `vault-mirage` |
| `template_ref` | TEXT | Example: `research-labs/vault-mirage@v1` |
| `runtime_type` | TEXT | `mock`, `local_process`, `modal`, `kubernetes_gvisor` |
| `runtime_instance_ref` | TEXT | Internal only |
| `status` | TEXT | `provisioning`, `active`, `dirty`, `running_tests`, `passed`, `failed`, `expired`, `destroyed`, `error` |
| `objective_progress` | INT | 0-4 for V1 |
| `started_at` | TIMESTAMP |  |
| `expires_at` | TIMESTAMP |  |
| `completed_at` | TIMESTAMP | Nullable |
| `destroyed_at` | TIMESTAMP | Nullable |

### `research_lab_files`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `session_id` | UUID | FK |
| `path` | TEXT | File path |
| `content` | TEXT | Latest user snapshot |
| `writable` | BOOLEAN | Must match manifest |
| `version` | INT | Increment on patch |
| `updated_at` | TIMESTAMP |  |

### `research_lab_test_runs`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `session_id` | UUID | FK |
| `status` | TEXT | `running`, `passed`, `failed`, `timeout`, `error` |
| `command` | TEXT | Predefined command only |
| `results_json` | JSONB | Structured test result list |
| `started_at` | TIMESTAMP |  |
| `finished_at` | TIMESTAMP | Nullable |

### `research_lab_terminal_events`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `session_id` | UUID | FK |
| `test_run_id` | UUID | Nullable FK |
| `sequence` | INT | Monotonic per session |
| `stream` | TEXT | `stdout`, `stderr`, `system` |
| `line` | TEXT | Terminal line |
| `created_at` | TIMESTAMP |  |

---

## API V1

Use `/api/v1/research-labs` rather than overloading existing `/api/v1/labs`, unless the current `/labs` module is explicitly renamed to Research Labs.

### List Labs

```http
GET /api/v1/research-labs
Authorization: Bearer <jwt>
```

Response:

```json
{
  "success": true,
  "data": [
    {
      "id": "rl-007",
      "slug": "vault-mirage",
      "title": "Vault Mirage",
      "difficulty": "intermediate",
      "estimated_time": "2-4 hours",
      "xp_reward": 250,
      "status": "active",
      "summary": "...",
      "objectives": ["..."]
    }
  ],
  "error": null
}
```

### Get Lab

```http
GET /api/v1/research-labs/{lab_id}
Authorization: Bearer <jwt>
```

Return learner-safe manifest only.

Do not include hidden tests, solutions, verifier internals, seed variants, or private fixture paths.

### Create Session

```http
POST /api/v1/research-labs/{lab_id}/sessions
Authorization: Bearer <jwt>
Content-Type: application/json
```

Response:

```json
{
  "success": true,
  "data": {
    "session_id": "uuid",
    "lab_id": "rl-007",
    "status": "active",
    "stage": "investigate",
    "expires_at": "timestamp",
    "allowed_files": ["programs/vault_mirage/src/lib.rs"],
    "entry_file": "programs/vault_mirage/src/lib.rs",
    "files": [
      {
        "path": "programs/vault_mirage/src/lib.rs",
        "language": "rust",
        "writable": true,
        "content": "..."
      }
    ],
    "terminal": [
      {
        "sequence": 1,
        "stream": "system",
        "line": "Environment ready. Edit the allowed file, then run tests."
      }
    ],
    "objectives": [
      {
        "label": "Inspect the vault health calculation",
        "completed": true
      }
    ]
  },
  "error": null
}
```

### Get Session

```http
GET /api/v1/research-labs/sessions/{session_id}
Authorization: Bearer <jwt>
```

Must enforce ownership.

### Patch Files

```http
PATCH /api/v1/research-labs/sessions/{session_id}/files
Authorization: Bearer <jwt>
Content-Type: application/json
```

Request:

```json
{
  "files": [
    {
      "path": "programs/vault_mirage/src/lib.rs",
      "content": "updated file content"
    }
  ]
}
```

Rules:

- Reject any path not in `allowed_files`.
- Reject path traversal.
- Reject binary content.
- Enforce max file size.
- Store snapshot before running tests.
- Mark session as `dirty`.

### Run Tests

```http
POST /api/v1/research-labs/sessions/{session_id}/run-tests
Authorization: Bearer <jwt>
```

Rules:

- Run only the predefined lab command.
- No arbitrary command input from frontend.
- Refuse concurrent runs for the same session.
- Enforce timeout.
- Enforce memory/CPU limits.
- Store terminal events and structured results.

Response can return immediately with a test run ID:

```json
{
  "success": true,
  "data": {
    "test_run_id": "uuid",
    "status": "running"
  },
  "error": null
}
```

Or it can block until complete for the first implementation:

```json
{
  "success": true,
  "data": {
    "test_run_id": "uuid",
    "status": "failed",
    "results": [
      {
        "id": "normal-deposit",
        "label": "test deposit accepts normal oracle input",
        "passed": true
      },
      {
        "id": "overflow-rejected",
        "label": "test overflow-shaped oracle input is rejected",
        "passed": false
      }
    ],
    "objective_progress": 3
  },
  "error": null
}
```

### Terminal Polling

```http
GET /api/v1/research-labs/sessions/{session_id}/terminal?after_sequence=10
Authorization: Bearer <jwt>
```

Response:

```json
{
  "success": true,
  "data": {
    "events": [
      {
        "sequence": 11,
        "stream": "stdout",
        "line": "Compiling vault_mirage..."
      }
    ],
    "latest_sequence": 11
  },
  "error": null
}
```

### Reset Session

```http
POST /api/v1/research-labs/sessions/{session_id}/reset
Authorization: Bearer <jwt>
```

Reset should:

- destroy or reset runtime state,
- restore initial file templates,
- clear test results,
- append terminal event,
- keep the same session or create a new session revision.

### Optional Submit

```http
POST /api/v1/research-labs/sessions/{session_id}/submit
Authorization: Bearer <jwt>
```

Do not implement until test passing and report flow are ready.

---

## Security Requirements

Non-negotiable:

- Never trust frontend completion state.
- Never expose hidden tests or verifier predicates.
- Never expose sandbox secrets.
- Never allow arbitrary command execution in V1.
- Never allow writes outside `allowed_files`.
- Enforce session ownership on every route.
- Enforce TTL and cleanup.
- Rate-limit session creation, reset, file patch, and test run.
- Strip secrets from sandbox environment.
- Disable or restrict outbound network from sandbox unless needed for cached dependencies.
- Store completion only after backend test/verifier passes.

Sandbox isolation:

- one sandbox per session or strongly isolated job per run,
- CPU and memory limits,
- max runtime timeout,
- no privileged container,
- no host filesystem mounts except controlled template/cache mounts,
- no production env variables.

---

## Test Plan

### Backend Unit/Integration

- `GET /research-labs` returns Vault Mirage.
- session creation stores session and file snapshots.
- file patch accepts only `programs/vault_mirage/src/lib.rs`.
- file patch rejects `../`, absolute paths, unknown files, and oversized content.
- run-tests executes only configured command.
- run-tests records terminal events in sequence.
- run-tests returns structured results.
- failing patch does not complete lab.
- passing patch advances objective progress.
- expired session cannot run tests.
- another user cannot access session.

### Runtime/Sandbox

- sandbox starts without production secrets.
- sandbox cannot read host files.
- sandbox cannot write outside session workspace.
- timeout kills runaway test.
- reset restores original template.

### Acceptance

- User can open Vault Mirage.
- User can edit the allowed Rust file.
- User can run tests.
- Initial vulnerable code fails the overflow/security test.
- Correct checked arithmetic passes all tests.
- Frontend can display terminal output and structured test results.

---

## Frontend Contract Needed

Once backend endpoints exist, frontend will replace the local mock in:

```txt
Rustopia/app/components/research-labs-section.tsx
Rustopia/app/lib/research-labs/lab-state.ts
```

Expected frontend behavior:

- create or restore session when opening lab,
- display backend files,
- PATCH allowed file edits,
- POST run-tests,
- poll terminal events,
- render structured test results,
- update objective progress from backend state,
- avoid local completion authority.

---

## Implementation Order

1. Add Research Labs API schemas.
2. Add session/file/test/terminal database models.
3. Add `SandboxRuntime` abstraction.
4. Implement local process runtime for backend development.
5. Build real Vault Mirage lab package with hidden tests.
6. Implement session create/get/reset.
7. Implement file patch.
8. Implement run-tests and terminal event capture.
9. Add ownership, TTL, limits, and path validation.
10. Wire frontend to backend.
11. Replace local mock completion with backend authority.
12. Add Modal or stronger sandbox runtime for production.

---

## References

- LiteSVM: https://github.com/LiteSVM/litesvm
- Mollusk: https://solana.com/docs/programs/testing/mollusk
- Surfpool: https://solana.com/docs/intro/installation/surfpool-cli-basics
- Modal Sandboxes: https://modal.com/docs/guide/sandboxes
- gVisor: https://gvisor.dev/docs/architecture_guide/intro/
