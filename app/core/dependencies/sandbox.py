from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from app.core.config.settings import get_settings
from app.core.database.session import get_db_session
from app.modules.sandbox.domain.runtime import SandboxRuntime
from app.modules.sandbox.infrastructure.litesvm_runtime import LiteSVMSandboxRuntime


def get_sandbox_runtime(session: AsyncSession = Depends(get_db_session)) -> SandboxRuntime:
    settings = get_settings()
    return LiteSVMSandboxRuntime(
        template_root=Path(settings.research_lab_template_root),
        workspace_root=Path(settings.research_lab_workspace_root),
        db_session=session,
    )
