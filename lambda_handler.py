import asyncio
import logging
import os

from mangum import Mangum

logging.basicConfig(level=logging.INFO)
_log = logging.getLogger("startup")
_log.info(
    "solbreach_lambda_coldstart stage=%s environment=%s deploy_version=%s deploy_commit_sha=%s",
    os.getenv("STAGE", ""),
    os.getenv("ENVIRONMENT", ""),
    os.getenv("DEPLOY_VERSION", ""),
    os.getenv("DEPLOY_COMMIT_SHA", ""),
)
_url = os.getenv("DATABASE_URL", "")
if _url:
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text

        async def _migrate() -> None:
            engine = create_async_engine(_url)
            async with engine.begin() as conn:
                for table, col, col_type, col_default, desc in [
                    ("research_lab_transactions", "idempotency_key", "VARCHAR(100)", "'legacy'", "idempotency_key"),
                    ("research_lab_transactions", "sequence_number", "INTEGER", "0", "sequence_number"),
                    ("research_lab_transactions", "parameters_json", "JSON", "'{}'::json", "parameters_json"),
                    ("research_lab_sessions", "impact_verified", "BOOLEAN", "false", "impact_verified"),
                    ("research_lab_sessions", "verified_evidence_refs_json", "JSON", "'[]'::json", "verified_evidence_refs_json"),
                    ("research_lab_sessions", "finding_review_passed", "BOOLEAN", "false", "finding_review_passed"),
                    ("research_lab_sessions", "finding_review_attempts", "INTEGER", "0", "finding_review_attempts"),
                    ("research_lab_sessions", "finding_review_score", "INTEGER", "0", "finding_review_score"),
                    ("research_lab_sessions", "finding_review_answers_json", "JSON", "'{}'::json", "finding_review_answers_json"),
                    ("research_lab_sessions", "failed_question_ids_json", "JSON", "'[]'::json", "failed_question_ids_json"),
                    ("research_lab_sessions", "critical_questions_passed", "BOOLEAN", "false", "critical_questions_passed"),
                    ("research_lab_sessions", "finding_review_feedback", "TEXT", None, "finding_review_feedback"),
                    ("research_lab_sessions", "audit_report_builder_passed", "BOOLEAN", "false", "audit_report_builder_passed"),
                    ("research_lab_transactions", "account_deltas_json", "JSON", "'[]'::json", "account_deltas_json"),
                    ("research_lab_transactions", "evidence_refs_json", "JSON", "'[]'::json", "evidence_refs_json"),
                    ("research_lab_transactions", "protocol_state_json", "JSON", "'{}'::json", "protocol_state_json"),
                    ("research_lab_transactions", "user_facing_evidence_json", "JSON", "'[]'::json", "user_facing_evidence_json"),
                ]:
                    r = await conn.execute(
                        text("SELECT 1 FROM information_schema.columns "
                             "WHERE table_name=:table "
                             "AND column_name=:col"),
                        {"table": table, "col": col},
                    )
                    if not r.scalar():
                        if col_default is None:
                            stmt = f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"
                        else:
                            stmt = (
                                f"ALTER TABLE {table} "
                                f"ADD COLUMN {col} {col_type} NOT NULL DEFAULT {col_default}"
                            )
                        await conn.execute(text(stmt))
                        _log.info(f"Added {desc} column")
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
