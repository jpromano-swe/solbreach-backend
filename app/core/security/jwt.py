from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from pydantic import BaseModel

from app.core.config.settings import Settings, get_settings
from app.core.exceptions.domain import UnauthorizedError

TokenType = Literal["access", "refresh"]


class TokenPayload(BaseModel):
    sub: str
    role: str
    type: TokenType
    exp: int


class JWTService:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def create_token(self, subject: str, role: str, token_type: TokenType) -> str:
        minutes = (
            self._settings.access_token_expire_minutes
            if token_type == "access"
            else self._settings.refresh_token_expire_minutes
        )
        expires_at = datetime.now(UTC) + timedelta(minutes=minutes)
        payload: dict[str, Any] = {
            "sub": subject,
            "role": role,
            "type": token_type,
            "exp": expires_at,
        }
        return jwt.encode(
            payload, self._settings.jwt_secret_key, algorithm=self._settings.jwt_algorithm
        )

    def decode(self, token: str, expected_type: TokenType = "access") -> TokenPayload:
        try:
            payload = jwt.decode(
                token,
                self._settings.jwt_secret_key,
                algorithms=[self._settings.jwt_algorithm],
            )
        except jwt.PyJWTError as exc:
            raise UnauthorizedError("Invalid token") from exc

        token_payload = TokenPayload.model_validate(payload)
        if token_payload.type != expected_type:
            raise UnauthorizedError("Invalid token type")
        return token_payload
