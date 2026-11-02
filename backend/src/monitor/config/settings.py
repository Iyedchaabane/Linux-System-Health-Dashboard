"""Application settings with validation and defaults."""

from typing import Literal

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="MONITOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Server
    host: str = Field(default="127.0.0.1", description="Bind address")
    port: int = Field(default=8080, ge=1, le=65535, description="Bind port")
    workers: int = Field(default=1, ge=1, description="Number of uvicorn workers")

    # Sampling
    sample_interval_seconds: float = Field(
        default=1.0, ge=1.0, le=10.0, description="Sampling interval (seconds)"
    )

    # WebSocket
    max_ws_clients: int = Field(
        default=100, ge=1, le=1000, description="Max concurrent WebSocket clients"
    )
    max_ws_clients_per_ip: int = Field(
        default=10, ge=1, le=100, description="Max WebSocket clients per IP"
    )
    ws_queue_size: int = Field(default=4, ge=1, le=100, description="Per-client message queue size")
    ws_send_timeout_seconds: float = Field(
        default=5.0, ge=0.5, le=30.0, description="WebSocket send timeout"
    )
    ws_handshake_timeout_seconds: float = Field(
        default=5.0, ge=0.5, le=30.0, description="WebSocket handshake timeout"
    )
    ws_max_message_size: int = Field(
        default=4096, ge=1024, le=1048576, description="Max inbound message size (bytes)"
    )
    ws_rate_limit_burst: int = Field(
        default=10, ge=1, le=100, description="Inbound message rate limit burst"
    )
    ws_rate_limit_refill: float = Field(
        default=2.0, ge=0.1, le=100.0, description="Inbound message rate limit refill per second"
    )

    # History
    history_max_seconds: int = Field(
        default=3600, ge=60, le=86400, description="History retention window (seconds)"
    )

    # Process listing
    max_processes_in_stream: int = Field(
        default=25, ge=1, le=100, description="Top-N processes in live stream"
    )
    max_processes_in_rest: int = Field(
        default=100, ge=1, le=500, description="Max processes in REST response"
    )

    # Snapshot size budget
    snapshot_size_budget_bytes: int = Field(
        default=16384, ge=4096, le=1048576, description="Snapshot JSON size budget"
    )

    # Environment
    environment: "Literal['development', 'testing', 'production']" = Field(
        default="development",
        description="Deployment environment",
    )

    # CORS and security
    allowed_origins: list[str] = Field(
        default_factory=list, description="Allowed CORS/WebSocket origins"
    )
    docs_enabled: bool = Field(default=True, description="Enable OpenAPI docs at /docs")

    # Logging
    log_level: str = Field(default="INFO", description="Log level")
    log_json: bool = Field(default=False, description="Use JSON log format")

    # Collection timeouts
    collection_timeout_multiplier: float = Field(
        default=3.0,
        ge=1.0,
        le=10.0,
        description="Collection timeout as multiple of sample interval",
    )

    @field_validator("allowed_origins")
    @classmethod
    def _validate_origin_security(cls, value: list[str], info: ValidationInfo) -> list[str]:
        """Optional security validation for allowed origins.

        For production, require at least one explicit origin and forbid
        wildcard entries. Development/testing keep the permissive defaults.
        """
        environment = info.data.get("environment", "development")
        if environment != "production":
            return value
        if not value:
            raise ValueError("allowed_origins must be non-empty in production")
        for origin in value:
            if "*" in origin:
                raise ValueError("wildcard origins are not allowed in production")
        return value


def load_settings() -> Settings:
    """Load and validate settings. Fails fast on invalid config."""
    return Settings()
