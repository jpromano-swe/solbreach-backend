import logging
from pathlib import Path

from alembic.config import Config
from alembic import command
from mangum import Mangum

logging.basicConfig(level=logging.INFO)
_log = logging.getLogger("migration")
_alembic_cfg = Path(__file__).parent / "alembic.ini"
try:
    cfg = Config(str(_alembic_cfg))
    command.upgrade(cfg, "head")
    _log.info("Database migration: upgrade head completed")
except Exception:
    _log.warning("Database migration: upgrade head failed (non-fatal)", exc_info=True)

from app.main import create_app

app = create_app()
stage = os.getenv("STAGE", "")
handler = Mangum(app, lifespan="off", api_gateway_base_path=f"/{stage}" if stage else None)