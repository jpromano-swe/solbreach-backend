# SolBreach Backend

Async FastAPI backend for SolBreach, structured as a modular monolith with hexagonal architecture.

## Stack

- Python 3.12+
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

Submissions are verified deterministically from proof payloads against each level's
`verification_config`. The backend does not execute user code, run uploaded scripts, deploy
validators, or orchestrate sandboxes.

Successful verification:

- marks the session completed
- records the verified submission
- awards XP once for that level
- unlocks the next sequential level
- unlocks the next sequential level

## Verification

```bash
poetry run pytest
poetry run ruff check .
```
