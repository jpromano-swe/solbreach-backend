# SolBreach Backend

Async FastAPI backend for SolBreach, structured as a modular monolith with hexagonal architecture.

It manages wallet authentication, beta access, onboarding, guided-level sessions,
Research Lab execution and reports, progression, badges, and certificate mint
authorization. The [frontend](https://github.com/jpromano-swe/solbreach/tree/research-labs-frontend)
contains the Anchor programs and the Next.js server that mints Bubblegum cNFTs.

This README describes the `backend-testing` branch. See the
[product README](https://github.com/jpromano-swe/solbreach/blob/research-labs-frontend/README.md)
for the beta, pitch, demo, devnet program addresses, and product scope.

## Stack

- Python 3.11+
- FastAPI 0.136.1
- PostgreSQL
- SQLAlchemy 2.0 async
- Alembic
- Pydantic v2
- JWT auth
- Poetry

## Run Locally

Clone the product branch and start PostgreSQL (Docker Compose is included):

```bash
git clone --branch backend-testing https://github.com/jpromano-swe/solbreach-backend.git
cd solbreach-backend
cp .env.example .env
docker compose up -d postgres
```

For a host-run API, set `DATABASE_URL` in `.env` to
`postgresql+asyncpg://solbreach:solbreach@localhost:5432/solbreach`.
The example uses `postgres`, which resolves inside Docker Compose, not on the host.
Set `APP_BASE_URL=http://localhost:3000` for a local frontend and replace
`JWT_SECRET_KEY` with a local random secret.

```bash
poetry install
poetry run alembic upgrade head
poetry run python -m app.scripts.seed_dev_data
poetry run uvicorn app.main:app --reload
```

Alternatively, run the API in Docker after copying `.env.example` to `.env`.
The container installs the main Python dependencies. Migrations and seed data
must still be applied explicitly:

```bash
docker compose up -d --build
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.scripts.seed_dev_data
```

API root:

```txt
http://localhost:8000
```

Health check:

```txt
GET /health
```

`GET /version` exposes deployment metadata; interactive API docs are at
`http://localhost:8000/docs`. Run seed data only in a development database: it
contains demo users, example resources, and synthetic proof/signature values.
It is not evidence of real on-chain activity or a production catalog.

## Architecture

Modules are organized into these layers:

```txt
domain -> application -> infrastructure -> presentation
```

Domain code defines entities and contracts, application code orchestrates use cases,
infrastructure contains persistence and runtime adapters, and presentation exposes
HTTP routes and schemas. Some application use cases currently import database models
and SQLAlchemy directly, so this is not a strict dependency boundary throughout.

Registered API modules (see [`app/main.py`](app/main.py)):

- `/api/v1/auth`
- `/api/v1/beta-access`
- `/api/v1/onboarding`
- `/api/v1/waitlist`
- `/api/v1/analytics`
- `/api/v1/badges`
- `/api/v1/users`
- `/api/v1/vulnerabilities`
- `/api/v1/levels`
- `/api/v1/submissions`
- `/api/v1/progress`
- `/api/v1/certifications`
- `/api/v1/certificates`
- `/api/v1/labs`
- `/api/v1/research-labs`

The frontend's Breach Rooms client targets `/api/v1/breach-rooms`, but this checkout
does not register those routes or implement its GitHub PR/webhook review service.
The frontend level 4–5 slugs (`level-4-data-matching`, `level-5-time-traveler`) also
have no matching seeded definitions here. The seeded Level 4 “Advanced Bounty
Drainer” is a different entry.

## MVP Gameplay Loop

Seeded development data includes a demo-ready Level 1 happy path plus locked follow-up
levels. The core loop is:

```txt
POST /api/v1/levels/{level_id}/start
GET  /api/v1/levels/{level_id}/status
POST /api/v1/levels/{level_id}/submit
```

Guided level submissions use configured proof and transaction checks. The devnet
adapter can fetch confirmed transactions from RPC; seed fixtures and modeled lab
results must not be presented as public devnet transactions.

Successful verification:

- marks the session completed
- records the verified submission
- awards XP once for that level
- unlocks the next sequential level

## Research Lab runtimes and assessment

| Lab                        | Runtime                                                                      | Evidence boundary                                                                                                                                                                                                                                 |
| -------------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| RL1 — Account Substitution | LiteSVM adapter, with a local simulation fallback on adapter import failure. | Loads a program and submits transactions, but also applies direct state adjustments and modeled successful transitions after failed deposit/withdraw transactions. A successful lab result does not by itself prove successful program execution. |
| RL2 — Yield Hijack         | `YieldHijackRuntime`, a Python state simulation.                             | Models stake/reward behavior and account deltas; no public devnet transaction or LiteSVM execution for these actions.                                                                                                                             |
| RL3 — Arbitrary CPI        | `ArbitraryCPIRuntime`, a Python state simulation.                            | The displayed build, deploy, and CPI steps validate inputs and update modeled session state; they do not compile and deploy learner code into LiteSVM.                                                                                            |

Runtime selection is in [`app/core/dependencies/sandbox.py`](app/core/dependencies/sandbox.py).
Both top-level adapters delegate RL2 and RL3 to the same Python implementations.
The in-app explorer displays sandbox session evidence, not public network history.

Lab completion combines impact verification, finding-review answers, and structured
report validation against predefined rules. It is not independent expert or AI-agent
review. The secure-pattern step does not provide general compiled patch verification.

Templates live in [`lab_templates/research-labs/`](lab_templates/research-labs/).
`RESEARCH_LAB_TEMPLATE_ROOT` defaults to `lab_templates` and
`RESEARCH_LAB_WORKSPACE_ROOT` to `/tmp/solbreach_research_labs`; run the API from
the repository root or configure explicit paths. Source-level runtime behavior
does not establish which adapter or revision a hosted deployment is running.

## Verification

```bash
poetry run pytest
poetry run ruff check .
```

## Certificate mint authorization — 2026-10-12

Run `poetry run alembic upgrade head` before deploying the matching frontend.
Migration `202610120001` adds persisted nonce consumption and wallet attempt records.

`POST /api/v1/certificates/mint-authorization` requires a bearer session, its linked
wallet, and an Ed25519 signed message containing the recipient, level, devnet,
issued-at timestamp and nonce. Authorization expires after five minutes; nonces are
single-use. PostgreSQL row locking serializes attempts across workers, with a limit
of five per wallet per ten minutes. Wallet authorization does **not** establish level
completion: the frontend mint server separately verifies backend completion or the
program-owned on-chain certificate PDA before using its server authority.

The Next.js mint server owns RPC/tree configuration and restricts minting to devnet.
Deploy this backend first, then the frontend. No user interview counts, partnerships
or paid usage claims are inferred from source code.

```bash
poetry run pytest tests/integration/test_mint_authorization.py tests/integration/test_certificates_flow.py
```
