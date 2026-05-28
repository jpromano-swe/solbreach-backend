import os
import subprocess
import sys
from pathlib import Path

from mangum import Mangum
from app.main import create_app

# Auto-run pending database migrations on cold start
_here = Path(__file__).parent
_alembic_cfg = str(_here / "alembic.ini")
try:
    subprocess.run(
        [sys.executable, "-m", "alembic", "--config", _alembic_cfg, "upgrade", "head"],
        cwd=str(_here),
        capture_output=True,
        text=True,
        timeout=30,
    )
except Exception:
    pass  # Non-fatal — app continues even if migration fails

app = create_app()
stage = os.getenv("STAGE", "")
handler = Mangum(app, lifespan="off", api_gateway_base_path=f"/{stage}" if stage else None)