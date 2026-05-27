from pathlib import Path

from app.core.config.settings import get_settings
from app.modules.sandbox.domain.runtime import SandboxRuntime
from app.modules.sandbox.infrastructure.local_process_runtime import LocalProcessSandboxRuntime


def get_sandbox_runtime() -> SandboxRuntime:
    settings = get_settings()
    return LocalProcessSandboxRuntime(
        template_root=Path(settings.research_lab_template_root),
        workspace_root=Path(settings.research_lab_workspace_root),
    )
