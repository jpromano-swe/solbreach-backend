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
                    await conn.execute(text(
                        "ALTER TABLE research_lab_transactions "
                        "ADD CONSTRAINT uq_research_lab_tx_idem UNIQUE (session_id, idempotency_key)"
                    ))
                    _log.info("Added idempotency_key column + constraint")
            await engine.dispose()

        import asyncio
        asyncio.run(_migrate())
    except Exception:
        _log.warning("Migration skipped (non-fatal)", exc_info=True)

from app.main import create_app

app = create_app()
stage = os.getenv("STAGE", "")
handler = Mangum(app, lifespan="off", api_gateway_base_path=f"/{stage}" if stage else None)