from functools import lru_cache
from typing import Annotated, Any, Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SolBreach API"
    environment: Literal["local", "dev","test", "staging", "production"] = "local"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False
    app_base_url: str = Field(
        default="https://beta.solbreach.com",
        validation_alias=AliasChoices("APP_BASE_URL", "FRONTEND_URL"),
    )

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

    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "https://solbreach.com",
            "https://www.solbreach.com",
            "https://beta.solbreach.com",
            "https://solbreach.vercel.app",
        ],
        validation_alias="CORS_ALLOWED_ORIGINS",
    )
    solana_devnet_rpc_url: str = Field(
        default="https://api.devnet.solana.com",
        validation_alias="SOLANA_DEVNET_RPC_URL",
    )
    research_lab_template_root: str = Field(
        default="lab_templates",
        validation_alias="RESEARCH_LAB_TEMPLATE_ROOT",
    )
    research_lab_workspace_root: str = Field(
        default="/tmp/solbreach_research_labs",
        validation_alias="RESEARCH_LAB_WORKSPACE_ROOT",
    )
    research_lab_session_ttl_hours: int = Field(
        default=4,
        validation_alias="RESEARCH_LAB_SESSION_TTL_HOURS",
    )
    research_lab_test_timeout_seconds: int = Field(
        default=120,
        validation_alias="RESEARCH_LAB_TEST_TIMEOUT_SECONDS",
    )
    research_lab_max_file_size_bytes: int = Field(
        default=100_000,
        validation_alias="RESEARCH_LAB_MAX_FILE_SIZE_BYTES",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str] | Any:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def validate_production_cors(self) -> "Settings":
        self.app_base_url = self.app_base_url.rstrip("/")
        if self.environment == "production" and "*" in self.cors_origins:
            raise ValueError("CORS wildcard origins are not allowed in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
