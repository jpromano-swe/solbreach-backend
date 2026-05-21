from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SolBreach API"
    environment: Literal["local", "test", "staging", "production"] = "local"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False

    database_url: str = Field(
        default="postgresql+asyncpg://solbreach:solbreach@postgres:5432/solbreach",
        validation_alias="DATABASE_URL",
    )

    jwt_secret_key: str = Field(
        default="change-me-in-production", validation_alias="JWT_SECRET_KEY"
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_minutes: int = 60 * 24 * 14

    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
