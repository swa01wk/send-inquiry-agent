"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import Literal

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
    openai_temperature: float = Field(default=0.6, validation_alias="OPENAI_TEMPERATURE")
    router_model: str | None = Field(default=None, validation_alias="ROUTER_MODEL")
    router_min_confidence: float = Field(default=0.6, validation_alias="ROUTER_MIN_CONFIDENCE")

    otp_mock_code: str = Field(default="1234", validation_alias="OTP_MOCK_CODE")
    # Mock inbox: the verification card carries the link token so a demo button can
    # stand in for clicking the emailed link. Turn off once real email is wired.
    email_link_demo: bool = Field(default=True, validation_alias="EMAIL_LINK_DEMO")
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
    # ---- Simulated Cenomi and dev tools (L3 §3.1–3.4) ----------------------------
    # Which implementations back the services. Only `mock` exists in the POC.
    integrations: Literal["mock", "sandbox", "live"] = Field(
        default="mock", validation_alias="INTEGRATIONS"
    )
    # Dev-only endpoints: /api/dev/outbox and /api/dev/audit/{id}. Mock integrations only.
    dev_tools: bool = Field(default=False, validation_alias="DEV_TOOLS")
    # Fault injection for mocks: "service:kind[:count],..." (kind: timeout|unavailable|rejected).
    mock_faults: str = Field(default="", validation_alias="MOCK_FAULTS")
    # Where restart-safe snapshots live (sessions, mock systems, audit). Empty = memory only.
    data_dir: str | None = Field(default=None, validation_alias="DATA_DIR")
    # Links in emails and SMS point at the frontend.
    public_base_url: str = Field(
        default="http://localhost:5173", validation_alias="PUBLIC_BASE_URL"
    )
    # Signs verification, resume and tracking links (HMAC-SHA256). Set a real secret outside dev.
    token_secret: str = Field(default="dev-only-change-me", validation_alias="RESUME_TOKEN_SECRET")
    email_link_ttl_hours: int = Field(default=72, validation_alias="EMAIL_LINK_TTL_HOURS")
    resume_ttl_days: int = Field(default=7, validation_alias="RESUME_TTL_DAYS")
    track_ttl_days: int = Field(default=365, validation_alias="TRACK_TTL_DAYS")
    # Human handoff (L3 §3.6): what the handoff card shows, and where mock cases are sent.
    # Placeholders until Cenomi confirms the real call-centre details.
    call_centre_phone: str = Field(default="+966 11 000 0000", validation_alias="CALL_CENTRE_PHONE")
    call_centre_email: str = Field(
        default="leasing-callcentre@example.com", validation_alias="CALL_CENTRE_EMAIL"
    )
    call_centre_hours: str = Field(
        default="Sunday to Thursday, 9 am to 5 pm (Riyadh time)",
        validation_alias="CALL_CENTRE_HOURS",
    )

    # Business-rule policy file (L3 §3.7); empty = the packaged app/policy/policy.yaml.
    policy_path: str | None = Field(default=None, validation_alias="POLICY_PATH")
    # Master data source (L3 §3.8): the generated seed JSON, or Cenomi's (stub until access).
    master_data_source: Literal["seed", "cenomi"] = Field(
        default="seed",
        validation_alias="MASTER_DATA_SOURCE",
    )
    # ---- Review lifecycle (L4) ----------------------------------------------------------
    # The reviewer console and /api/review/* (mock integrations only).
    reviewer_console: bool = Field(default=False, validation_alias="REVIEWER_CONSOLE")
    # Attempts to send an approved lead to Yardi before the case is flagged for operations.
    yardi_max_attempts: int = Field(default=3, ge=1, le=10, validation_alias="YARDI_MAX_ATTEMPTS")
    # The backend's own address, for links that hit the API (the mock Azure AD accept link).
    public_api_url: str = Field(default="http://localhost:8000", validation_alias="PUBLIC_API_URL")
    case_ttl_days: int = Field(default=30, validation_alias="CASE_TTL_DAYS")
    # Testing only: treat the model as unavailable, so every turn runs in form mode (L3 §3.14).
    form_mode: bool = Field(default=False, validation_alias="FORM_MODE")
    # Intake channels (mock integrations only): the call-centre console and Tenant Central.
    callcentre_console: bool = Field(default=False, validation_alias="CALLCENTRE_CONSOLE")
    tenant_portal: bool = Field(default=False, validation_alias="TENANT_PORTAL")
    # Proactive work (L5): a background tick evaluates triggers every N seconds.
    proactive_enabled: bool = Field(default=False, validation_alias="PROACTIVE_ENABLED")
    proactive_tick_seconds: int = Field(
        default=60, ge=5, le=3600, validation_alias="PROACTIVE_TICK_SECONDS"
    )
    agent_mode: Literal["openai", "scripted"] = Field(
        default="openai",
        validation_alias="AGENT_MODE",
    )

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
