from typing import Protocol


class TokenService(Protocol):
    def create_token(self, subject: str, role: str, token_type: str) -> str: ...
