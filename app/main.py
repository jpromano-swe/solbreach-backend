from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config.settings import get_settings
from app.core.exceptions.handlers import register_exception_handlers
from app.core.logging.setup import configure_logging
from app.core.middleware.request_id import RequestIDMiddleware
from app.modules.analytics.presentation.api.routes import router as analytics_router
from app.modules.auth.presentation.api.routes import router as auth_router
from app.modules.certifications.presentation.api.routes import router as certifications_router
from app.modules.labs.presentation.api.research_lab_routes import (
    router as research_labs_router,
)
from app.modules.labs.presentation.api.routes import router as labs_router
from app.modules.levels.presentation.api.routes import router as levels_router
from app.modules.progress.presentation.api.routes import router as progress_router
from app.modules.submissions.presentation.api.routes import router as submissions_router
from app.modules.users.presentation.api.routes import router as users_router
from app.modules.vulnerabilities.presentation.api.routes import router as vulnerabilities_router
import os


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    stage = os.getenv("STAGE","")
    root_path = f"/{stage}" if stage else ""
    app = FastAPI(title=settings.app_name, debug=settings.debug, root_path=root_path,)

    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    prefix = settings.api_v1_prefix
    app.include_router(auth_router, prefix=f"{prefix}/auth", tags=["auth"])
    app.include_router(analytics_router, prefix=f"{prefix}/analytics", tags=["analytics"])
    app.include_router(users_router, prefix=f"{prefix}/users", tags=["users"])
    app.include_router(
        vulnerabilities_router, prefix=f"{prefix}/vulnerabilities", tags=["vulnerabilities"]
    )
    app.include_router(levels_router, prefix=f"{prefix}/levels", tags=["levels"])
    app.include_router(submissions_router, prefix=f"{prefix}/submissions", tags=["submissions"])
    app.include_router(progress_router, prefix=f"{prefix}/progress", tags=["progress"])
    app.include_router(
        certifications_router, prefix=f"{prefix}/certifications", tags=["certifications"]
    )
    app.include_router(labs_router, prefix=f"{prefix}/labs", tags=["labs"])
    app.include_router(
        research_labs_router, prefix=f"{prefix}/research-labs", tags=["research-labs"]
    )

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "stage": os.getenv("STAGE", ""),
            "environment": os.getenv("ENVIRONMENT", ""),
            "deploy_version": os.getenv("DEPLOY_VERSION", ""),
            "deploy_commit_sha": os.getenv("DEPLOY_COMMIT_SHA", ""),
        }

    return app


app = create_app()
