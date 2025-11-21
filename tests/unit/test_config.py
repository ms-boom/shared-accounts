"""Unit tests for bot/core/config.py."""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from bot.core.config import Settings, get_settings


@pytest.mark.unit
class TestSettings:
    """Tests for Settings configuration class."""

    def test_creates_settings_with_valid_token(self, temp_dir: Path) -> None:
        """Test that Settings can be created with valid token."""
        os.environ["TELEGRAM_TOKEN"] = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"

        settings = Settings(
            TELEGRAM_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            DATA_DIR=temp_dir,
        )

        assert settings.TELEGRAM_TOKEN == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        assert settings.DEBUG is False
        assert settings.LOG_LEVEL == "INFO"

    def test_validates_telegram_token_not_empty(self) -> None:
        """Test that empty TELEGRAM_TOKEN raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(TELEGRAM_TOKEN="")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "TELEGRAM_TOKEN is required" in str(errors[0]["ctx"]["error"])

    def test_validates_telegram_token_not_whitespace(self) -> None:
        """Test that whitespace-only TELEGRAM_TOKEN raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(TELEGRAM_TOKEN="   ")

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "TELEGRAM_TOKEN is required" in str(errors[0]["ctx"]["error"])

    def test_strips_telegram_token_whitespace(self) -> None:
        """Test that TELEGRAM_TOKEN strips leading/trailing whitespace."""
        os.environ["TELEGRAM_TOKEN"] = "  123456:test  "

        settings = Settings(TELEGRAM_TOKEN="  123456:test  ")

        assert settings.TELEGRAM_TOKEN == "123456:test"

    def test_validates_log_level(self) -> None:
        """Test that invalid LOG_LEVEL raises validation error."""
        os.environ["TELEGRAM_TOKEN"] = "123456:test"

        with pytest.raises(ValidationError) as exc_info:
            Settings(
                TELEGRAM_TOKEN="123456:test",
                LOG_LEVEL="INVALID",
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "LOG_LEVEL must be one of" in str(errors[0]["ctx"]["error"])

    def test_converts_log_level_to_uppercase(self) -> None:
        """Test that LOG_LEVEL is converted to uppercase."""
        os.environ["TELEGRAM_TOKEN"] = "123456:test"

        settings = Settings(
            TELEGRAM_TOKEN="123456:test",
            LOG_LEVEL="debug",
        )

        assert settings.LOG_LEVEL == "DEBUG"

    def test_accepts_valid_log_levels(self) -> None:
        """Test that all valid log levels are accepted."""
        os.environ["TELEGRAM_TOKEN"] = "123456:test"
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        for level in valid_levels:
            settings = Settings(
                TELEGRAM_TOKEN="123456:test",
                LOG_LEVEL=level,
            )
            assert settings.LOG_LEVEL == level

    def test_converts_string_paths_to_path_objects(self) -> None:
        """Test that string paths are converted to Path objects."""
        os.environ["TELEGRAM_TOKEN"] = "123456:test"

        settings = Settings(
            TELEGRAM_TOKEN="123456:test",
            DATA_DIR=Path("/tmp/data"),
            SESSION_DIR=Path("/tmp/sessions"),
            LOG_DIR=Path("/tmp/logs"),
            ERROR_DIR=Path("/tmp/errors"),
        )

        assert isinstance(settings.DATA_DIR, Path)
        assert isinstance(settings.SESSION_DIR, Path)
        assert isinstance(settings.LOG_DIR, Path)
        assert isinstance(settings.ERROR_DIR, Path)

        assert settings.DATA_DIR == Path("/tmp/data")
        assert settings.SESSION_DIR == Path("/tmp/sessions")
        assert settings.LOG_DIR == Path("/tmp/logs")
        assert settings.ERROR_DIR == Path("/tmp/errors")

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        os.environ["TELEGRAM_TOKEN"] = "123456:test"
        # Remove DATABASE_URL from environment to use default
        os.environ.pop("DATABASE_URL", None)

        settings = Settings(TELEGRAM_TOKEN="123456:test")

        # Check DATABASE_URL default value (SQLite)
        assert settings.DATABASE_URL == "sqlite+aiosqlite:////data/claude_bot.db"
        assert settings.LOG_LEVEL == "INFO"
        assert settings.DEBUG is False
        assert settings.PERMISSION_CACHE_TTL == 300
        assert settings.PLAYWRIGHT_HEADLESS is True
        assert settings.PLAYWRIGHT_TIMEOUT == 30000
        assert settings.WORKER_POLL_INTERVAL == 1.0
        assert settings.WORKER_RETRY_ATTEMPTS == 3
        assert settings.WORKER_RETRY_BACKOFF == "2,4,8"

    def test_get_settings_returns_settings_instance(self) -> None:
        """Test that get_settings() returns Settings instance."""
        os.environ["TELEGRAM_TOKEN"] = "123456:test"

        settings = get_settings()

        assert isinstance(settings, Settings)
        assert settings.TELEGRAM_TOKEN == "123456:test"
