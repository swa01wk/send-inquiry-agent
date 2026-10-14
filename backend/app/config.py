"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration from docs/spec.md section 10."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_model: str | None = Field(default=None, validation_alias="OPENAI_MODEL")

    otp_mock_code: str = Field(default="1234", validation_alias="OTP_MOCK_CODE")
    max_upload_mb: int = Field(default=5, validation_alias="MAX_UPLOAD_MB")
    upload_dir: str = Field(default="./.uploads", validation_alias="UPLOAD_DIR")
    session_ttl_minutes: int = Field(default=120, validation_alias="SESSION_TTL_MINUTES")
    rate_limit_session: str = Field(default="30/minute", validation_alias="RATE_LIMIT_SESSION")
    rate_limit_ip: str = Field(default="60/minute", validation_alias="RATE_LIMIT_IP")
    cors_origins: str = Field(
        default="http://localhost:5173",
        validation_alias="CORS_ORIGINS",
    )
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    @property
    def cors_origin_list(self) -> list[str]:
        if not self.cors_origins.strip():
            return ["http://localhost:5173"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def require_openai(self) -> tuple[str, str]:
        """Return (api_key, model) or raise if agent features need OpenAI but env is missing."""
        if not self.openai_api_key or not self.openai_model:
            msg = "OPENAI_API_KEY and OPENAI_MODEL must be set to run the agent"
            raise RuntimeError(msg)
        return self.openai_api_key, self.openai_model


@lru_cache
def get_settings() -> Settings:
    return Settings()
