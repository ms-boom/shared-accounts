"""Application configuration using Pydantic Settings."""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.fingerprint import (
    validate_cpu_cores,
    validate_device_memory,
    validate_locale,
    validate_timezone,
    validate_user_agent,
)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram Bot Configuration
    TELEGRAM_TOKEN: str = Field(
        description="Bot token from @BotFather",
    )

    # Database Configuration (SQLite only)
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:////data/claude_bot.db",
        description="SQLite database connection URL",
    )

    # Logging Configuration
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log message format",
    )

    # Application Settings
    DEBUG: bool = Field(
        default=False,
        description="Enable debug mode",
    )

    # Permission Cache Settings
    PERMISSION_CACHE_TTL: int = Field(
        default=300,
        description="Permission cache TTL in seconds (default: 5 minutes)",
    )

    # Claude Authorization Bot Settings
    DATA_DIR: Path = Field(
        default=Path("/data"),
        description="Base directory for data storage",
    )
    SESSION_DIR: Path = Field(
        default=Path("/data/sessions"),
        description="Directory for Playwright browser sessions",
    )
    LOG_DIR: Path = Field(
        default=Path("/data/logs"),
        description="Directory for log files",
    )
    ERROR_DIR: Path = Field(
        default=Path("/data/errors"),
        description="Directory for error screenshots",
    )

    # Debug Settings
    BROWSER_DEBUG: bool = Field(
        default=False,
        description="Enable browser debug mode (save screenshots + HTML on each step)",
    )

    # Playwright Settings
    PLAYWRIGHT_HEADLESS: bool = Field(
        default=True,
        description="Run Playwright in headless mode",
    )
    PLAYWRIGHT_TIMEOUT: int = Field(
        default=60000,
        description="Playwright operation timeout in milliseconds (default: 60s)",
    )

    # Worker Settings
    WORKER_POLL_INTERVAL: float = Field(
        default=1.0,
        description="Worker task polling interval in seconds",
    )
    WORKER_RETRY_ATTEMPTS: int = Field(
        default=3,
        description="Number of retry attempts for failed operations",
    )
    WORKER_RETRY_BACKOFF: str = Field(
        default="2,4,8",
        description="Retry backoff delays in seconds (comma-separated)",
    )
    TASK_STUCK_TIMEOUT: int = Field(
        default=5,
        description="Minutes after which task in 'processing' status is considered stuck",
    )
    TASK_RECOVERY_INTERVAL: int = Field(
        default=60,
        description="Interval in seconds for stuck task recovery checks",
    )

    # Default browser fingerprint profile (applied when a session has no
    # per-session override — see src/core/fingerprint.py for the value objects
    # and validators shared with the FSM step validators).
    DEFAULT_USER_AGENT: str = Field(
        default=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
        ),
        description="Default User-Agent for browser sessions without an override",
    )
    DEFAULT_CPU_CORES: int = Field(
        default=8,
        description="Default navigator.hardwareConcurrency (1-32)",
    )
    DEFAULT_DEVICE_MEMORY: int = Field(
        default=8,
        description="Default navigator.deviceMemory in GB (1, 2, 4, or 8)",
    )
    DEFAULT_TIMEZONE: str = Field(
        default="America/New_York",
        description="Default IANA timezone for browser sessions without an override",
    )
    DEFAULT_LOCALE: str = Field(
        default="en-US",
        description="Default locale for browser sessions without an override",
    )

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_sqlite_url(cls, value: str) -> str:
        """Validate that DATABASE_URL uses SQLite. Only SQLite is supported."""
        if not value.lower().startswith("sqlite"):
            raise ValueError(
                f"Only SQLite is supported. DATABASE_URL must start with 'sqlite', "
                f"got: '{value[:20]}...'"
            )
        return value

    @field_validator("DATA_DIR", "SESSION_DIR", "LOG_DIR", "ERROR_DIR")
    @classmethod
    def ensure_path(cls, value: Path | str) -> Path:
        """Ensure value is a Path object."""
        return Path(value) if isinstance(value, str) else value

    @field_validator("TELEGRAM_TOKEN")
    @classmethod
    def validate_telegram_token(cls, value: str) -> str:
        """Validate that Telegram token is not empty."""
        if not value or not value.strip():
            raise ValueError("TELEGRAM_TOKEN is required and cannot be empty")
        return value.strip()

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Validate that log level is valid."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        value_upper = value.upper()
        if value_upper not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}, got '{value}'")
        return value_upper

    @field_validator("DEFAULT_USER_AGENT")
    @classmethod
    def validate_default_user_agent(cls, value: str) -> str:
        """Delegate to the shared fingerprint validator (single source of truth)."""
        return validate_user_agent(value)

    @field_validator("DEFAULT_CPU_CORES")
    @classmethod
    def validate_default_cpu_cores(cls, value: int) -> int:
        """Delegate to the shared fingerprint validator (single source of truth)."""
        return validate_cpu_cores(value)

    @field_validator("DEFAULT_DEVICE_MEMORY")
    @classmethod
    def validate_default_device_memory(cls, value: int) -> int:
        """Delegate to the shared fingerprint validator (single source of truth)."""
        return validate_device_memory(value)

    @field_validator("DEFAULT_TIMEZONE")
    @classmethod
    def validate_default_timezone(cls, value: str) -> str:
        """Delegate to the shared fingerprint validator (single source of truth)."""
        return validate_timezone(value)

    @field_validator("DEFAULT_LOCALE")
    @classmethod
    def validate_default_locale(cls, value: str) -> str:
        """Delegate to the shared fingerprint validator (single source of truth)."""
        return validate_locale(value)


def get_settings() -> Settings:
    """Get application settings instance.

    Creates Settings by reading from environment variables and .env file.
    Pydantic Settings handles __init__ through metaclass, so mypy doesn't
    understand the signature. We use model_validate to make it explicit.
    """
    # Using empty dict tells pydantic to read from environment
    return Settings.model_validate({})
