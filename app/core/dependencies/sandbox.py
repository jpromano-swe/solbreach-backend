from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from app.core.config.settings import get_settings
from app.core.database.session import get_db_session
from app.modules.sandbox.domain.runtime import SandboxRuntime
from app.modules.sandbox.infrastructure.local_process_runtime import LocalProcessSandboxRuntime


def get_sandbox_runtime(session: AsyncSession = Depends(get_db_session)) -> SandboxRuntime:
    settings = get_settings()
    template_root = Path(settings.research_lab_template_root)
    workspace_root = Path(settings.research_lab_workspace_root)
    try:
        from app.modules.sandbox.infrastructure.litesvm_runtime import LiteSVMSandboxRuntime

        return LiteSVMSandboxRuntime(
            template_root=template_root,
            workspace_root=workspace_root,
            db_session=session,
        )
    except ImportError:
        return LocalProcessSandboxRuntime(
            template_root=template_root,
            workspace_root=workspace_root,
        )
