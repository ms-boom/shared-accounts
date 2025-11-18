"""Application configuration using Pydantic Settings."""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Database Configuration (PostgreSQL only)
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://user:password@localhost/claude_bot",
        description="PostgreSQL database connection URL",
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

    # Playwright Settings
    PLAYWRIGHT_HEADLESS: bool = Field(
        default=True,
        description="Run Playwright in headless mode",
    )
    PLAYWRIGHT_TIMEOUT: int = Field(
        default=30000,
        description="Playwright operation timeout in milliseconds (default: 30s)",
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


def get_settings() -> Settings:
    """Get application settings instance."""
    return Settings()  # type: ignore[call-arg]
