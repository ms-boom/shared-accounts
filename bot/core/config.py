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

    # Database Configuration
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./bot.db",
        description="Database connection URL",
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

    # FSM Storage Configuration
    FSM_STORAGE_TYPE: str = Field(
        default="memory",
        description="FSM storage type: 'memory' or 'redis'",
    )
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL (used if FSM_STORAGE_TYPE=redis)",
    )

    # Permission Cache Settings
    PERMISSION_CACHE_TTL: int = Field(
        default=300,
        description="Permission cache TTL in seconds (default: 5 minutes)",
    )

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
            raise ValueError(
                f"LOG_LEVEL must be one of {valid_levels}, got '{value}'"
            )
        return value_upper

    @field_validator("FSM_STORAGE_TYPE")
    @classmethod
    def validate_fsm_storage_type(cls, value: str) -> str:
        """Validate that FSM storage type is valid."""
        valid_types = {"memory", "redis"}
        value_lower = value.lower()
        if value_lower not in valid_types:
            raise ValueError(
                f"FSM_STORAGE_TYPE must be one of {valid_types}, got '{value}'"
            )
        return value_lower


def get_settings() -> Settings:
    """Get application settings instance."""
    return Settings()
