# SolBreach Backend

Async FastAPI backend for SolBreach, structured as a modular monolith with hexagonal architecture.

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

```bash
cp .env.example .env
poetry install
poetry run alembic upgrade head
poetry run python -m app.scripts.seed_dev_data
poetry run uvicorn app.main:app --reload
```

Docker:

```bash
cp .env.example .env
docker compose up --build
```

API root:

```txt
http://localhost:8000
```

Health check:

```txt
GET /health
```

## Architecture

Each module follows the same boundary:

```txt
domain -> application -> infrastructure -> presentation
```

Domain and application code do not depend on FastAPI or SQLAlchemy. Adapters live in infrastructure and presentation.

Initial API modules:

- `/api/v1/auth`
- `/api/v1/users`
- `/api/v1/vulnerabilities`
- `/api/v1/levels`
- `/api/v1/submissions`
- `/api/v1/progress`
- `/api/v1/certifications`
- `/api/v1/labs`

## MVP Gameplay Loop

Seeded development data includes a demo-ready Level 1 happy path plus locked follow-up
levels. The core loop is:

```txt
POST /api/v1/levels/{level_id}/start
GET  /api/v1/levels/{level_id}/status
POST /api/v1/levels/{level_id}/submit
```

Guided level submissions use configured proof and transaction checks. Research Labs
have separate runtimes: RL1 includes an optional LiteSVM adapter, while other lab flows
include deterministic modeled state transitions. These are not a general uploaded-code
verification service, and modeled results must not be presented as devnet transactions.

Successful verification:

- marks the session completed
- records the verified submission
- awards XP once for that level
- unlocks the next sequential level

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
