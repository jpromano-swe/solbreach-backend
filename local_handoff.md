Handoff — Local SolBreach Backend Setup on Secondary Windows PC
Context
We are migrating the SolBreach backend away from funded cloud infra and into a local backend environment running on a secondary Windows PC, which will act as a temporary backend host for testing and demo support.
The goal is:
run solbreach_backend locally on that PC
expose it via ngrok
later point the frontend testing branch to the ngrok URL
keep the main dev workflow on the primary machine unchanged
This secondary PC should behave like a lightweight service box, not as the main development machine.
Current status
We are in Phase 1: local backend setup.
What has already been done
The repo has already been cloned on the secondary PC.
We are inside the backend setup process.
We already created the initial plan:clone repo
configure backend locally
run Postgres
run migrations
seed data
run backend on localhost
expose via ngrok
later connect frontend testing branch

Current exact step
We are currently at Step 4: install Poetry and prepare Python environment.
Important environment facts
OS
Windows
using PowerShell
Python currently installed
Python 3.10.11
Important concern
The backend README says the backend stack is:
Python 3.12+
So the main risk right now is:
Poetry installation itself may work with Python 3.10
but the backend may require Python 3.12 to install or run correctly
We have not yet fully confirmed the pyproject.toml Python constraint on that PC during this step, but we should assume Python 3.12 is likely required unless proven otherwise.
Relevant backend repo facts
Backend path
The work is happening in:
solbreach_backend
Backend local run path expected
The backend should eventually run as:
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
Existing local backend setup plan
We intend to do:
create .env
run Postgres
install Poetry
install dependencies with Poetry
run Alembic migrations
seed dev/demo data
start FastAPI locally
verify /health
only then move to ngrok
Current .env intended local configuration
We already planned to use something like this for local execution:
ENVIRONMENT=local
DATABASE_URL=postgresql+asyncpg://solbreach:solbreach@localhost:5432/solbreach
JWT_SECRET_KEY=replace-with-a-long-random-secret
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
SOLANA_DEVNET_RPC_URL=https://api.devnet.solana.com
RESEARCH_LAB_TEMPLATE_ROOT=lab_templates
RESEARCH_LAB_WORKSPACE_ROOT=/tmp/solbreach_research_labs
RESEARCH_LAB_SESSION_TTL_HOURS=4
RESEARCH_LAB_TEST_TIMEOUT_SECONDS=120
RESEARCH_LAB_MAX_FILE_SIZE_BYTES=100000
DEPLOY_VERSION=local-ngrok
DEPLOY_COMMIT_SHA=local
The exact .env may still need Windows/local adjustments later, but this is the intended base.
What the agent should help with right now
The main job right now is to help through terminal-level setup issues on Windows PowerShell.
Specifically:
Immediate tasks
inspect pyproject.tomlconfirm exact Python version constraint

determine whether Python 3.10 is usableor whether Python 3.12 must be installed first

help install Poetry correctly on Windows PowerShell
help point Poetry to the correct Python interpreter
help run:poetry install

after that, continue with:Postgres
migrations
seeding
local backend boot

Known likely command path
If Python 3.12 is required
The likely safe path is:
install Python 3.12
verify:
py -3.12 --version
install Poetry with 3.12:
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -3.12 -
inside backend project:
poetry env use 3.12
poetry install
If Poetry is installed but not found in PATH
Need to troubleshoot Windows Poetry path resolution in PowerShell.
Constraints / preferences
Important preference
We want the secondary PC to remain a clean hosting machine.
That means:
prefer stable setup
avoid experimental local hacks
avoid unnecessary project edits during setup
focus on getting backend healthy and running first
Do not move ahead to ngrok yet
ngrok is not the current step.
Before ngrok, all of these must be working:
Python version correct
Poetry installed
dependencies installed
Postgres running
migrations pass
seed script passes
backend starts locally
/health responds
What the agent should optimize for
The agent should act like a Windows terminal setup assistant and focus on:
PowerShell compatibility
Poetry installation issues
Python version compatibility
backend dependency installation
migration/runtime readiness
Do not jump ahead into frontend/ngrok changes yet unless Phase 1 is complete.
Definition of success for the current phase
This phase is successful when:
Python version is correct for backend requirements
Poetry is installed and callable from PowerShell
poetry install succeeds in solbreach_backend
Only after that should the setup continue.
If the agent needs a concise summary
We are setting up solbreach_backend on a secondary Windows PC to run locally and later expose through ngrok. The repo is already cloned. We are currently blocked in Phase 1 at Poetry/Python setup. Python 3.10.11 is currently installed, but the backend likely needs Python 3.12+. Help verify the Python constraint from pyproject.toml, install the correct Python version if needed, install Poetry in PowerShell, and get poetry install working.