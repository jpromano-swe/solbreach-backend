from app.modules.sandbox.domain.runtime import SandboxRuntime


class ModalSandboxRuntime(SandboxRuntime):
    """Production adapter placeholder.

    The Labs module depends on SandboxRuntime, so this can be filled in later
    without changing the API/use-case layer.
    """

    async def create_session(self, session_id: str, template_ref: str) -> str:
        raise NotImplementedError("Modal sandbox runtime is not configured yet")

    async def hydrate_template(self, session_id: str, template_ref: str) -> None:
        raise NotImplementedError("Modal sandbox runtime is not configured yet")

    async def read_file(self, session_id: str, path: str) -> str:
        raise NotImplementedError("Modal sandbox runtime is not configured yet")

    async def patch_file(self, session_id: str, path: str, content: str) -> None:
        raise NotImplementedError("Modal sandbox runtime is not configured yet")

    async def run_tests(self, session_id: str, command: str, timeout_seconds: int):
        raise NotImplementedError("Modal sandbox runtime is not configured yet")

    async def reset_session(self, session_id: str, template_ref: str) -> None:
        raise NotImplementedError("Modal sandbox runtime is not configured yet")

    async def destroy_session(self, session_id: str) -> None:
        raise NotImplementedError("Modal sandbox runtime is not configured yet")

    async def get_visible_accounts(self, session_id: str):
        raise NotImplementedError("Modal sandbox runtime is not configured yet")

    async def get_account_state(self, session_id: str, account_ref: str):
        raise NotImplementedError("Modal sandbox runtime is not configured yet")

    async def submit_transaction(self, session_id: str, action_type: str, parameters: dict):
        raise NotImplementedError("Modal sandbox runtime is not configured yet")

    async def get_transaction_logs(self, session_id: str, transaction_ref: str):
        raise NotImplementedError("Modal sandbox runtime is not configured yet")

    async def verify_objective(self, session_id: str, objective_ref: str):
        raise NotImplementedError("Modal sandbox runtime is not configured yet")
