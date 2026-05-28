import asyncio
import logging
import os

from mangum import Mangum

logging.basicConfig(level=logging.INFO)
_log = logging.getLogger("startup")
_url = os.getenv("DATABASE_URL", "")
if _url:
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text

        async def _migrate() -> None:
            engine = create_async_engine(_url)
            async with engine.begin() as conn:
                r = await conn.execute(
                    text("SELECT 1 FROM information_schema.columns "
                         "WHERE table_name='research_lab_transactions' "
                         "AND column_name='idempotency_key'")
                )
                if not r.scalar():
                    await conn.execute(text(
                        "ALTER TABLE research_lab_transactions "
                        "ADD COLUMN idempotency_key VARCHAR(100) NOT NULL DEFAULT 'legacy'"
                    ))
                    _log.info("Added idempotency_key column (no constraint — handled in app layer)")
            await engine.dispose()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_migrate())
        _log.info("Startup migration complete")
    except Exception:
        _log.warning("Migration skipped (non-fatal)", exc_info=True)

from app.main import create_app

app = create_app()
stage = os.getenv("STAGE", "")
handler = Mangum(app, lifespan="off", api_gateway_base_path=f"/{stage}" if stage else None)