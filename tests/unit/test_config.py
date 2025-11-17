"""Unit tests for bot/core/config.py."""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from bot.core.config import Settings, get_settings


@pytest.mark.unit
def test_creates_settings_with_valid_token(temp_dir: Path) -> None:
    """Test that Settings can be created with valid token."""
    os.environ["TELEGRAM_TOKEN"] = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"

    settings = Settings(
        TELEGRAM_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        DATA_DIR=temp_dir,
    )

    assert settings.TELEGRAM_TOKEN == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    assert settings.DEBUG is False
    assert settings.LOG_LEVEL == "INFO"


@pytest.mark.unit
def test_validates_telegram_token_not_empty() -> None:
    """Test that empty TELEGRAM_TOKEN raises validation error."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(TELEGRAM_TOKEN="")

    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert "TELEGRAM_TOKEN is required" in str(errors[0]["ctx"]["error"])


@pytest.mark.unit
def test_validates_telegram_token_not_whitespace() -> None:
    """Test that whitespace-only TELEGRAM_TOKEN raises validation error."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(TELEGRAM_TOKEN="   ")

    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert "TELEGRAM_TOKEN is required" in str(errors[0]["ctx"]["error"])


@pytest.mark.unit
def test_strips_telegram_token_whitespace() -> None:
    """Test that TELEGRAM_TOKEN strips leading/trailing whitespace."""
    os.environ["TELEGRAM_TOKEN"] = "  123456:test  "

    settings = Settings(TELEGRAM_TOKEN="  123456:test  ")

    assert settings.TELEGRAM_TOKEN == "123456:test"


@pytest.mark.unit
def test_validates_log_level() -> None:
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


@pytest.mark.unit
def test_converts_log_level_to_uppercase() -> None:
    """Test that LOG_LEVEL is converted to uppercase."""
    os.environ["TELEGRAM_TOKEN"] = "123456:test"

    settings = Settings(
        TELEGRAM_TOKEN="123456:test",
        LOG_LEVEL="debug",
    )

    assert settings.LOG_LEVEL == "DEBUG"


@pytest.mark.unit
def test_accepts_valid_log_levels() -> None:
    """Test that all valid log levels are accepted."""
    os.environ["TELEGRAM_TOKEN"] = "123456:test"
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    for level in valid_levels:
        settings = Settings(
            TELEGRAM_TOKEN="123456:test",
            LOG_LEVEL=level,
        )
        assert settings.LOG_LEVEL == level


@pytest.mark.unit
def test_validates_fsm_storage_type() -> None:
    """Test that invalid FSM_STORAGE_TYPE raises validation error."""
    os.environ["TELEGRAM_TOKEN"] = "123456:test"

    with pytest.raises(ValidationError) as exc_info:
        Settings(
            TELEGRAM_TOKEN="123456:test",
            FSM_STORAGE_TYPE="invalid",
        )

    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert "FSM_STORAGE_TYPE must be one of" in str(errors[0]["ctx"]["error"])


@pytest.mark.unit
def test_converts_fsm_storage_type_to_lowercase() -> None:
    """Test that FSM_STORAGE_TYPE is converted to lowercase."""
    os.environ["TELEGRAM_TOKEN"] = "123456:test"

    settings = Settings(
        TELEGRAM_TOKEN="123456:test",
        FSM_STORAGE_TYPE="MEMORY",
    )

    assert settings.FSM_STORAGE_TYPE == "memory"


@pytest.mark.unit
def test_accepts_valid_fsm_storage_types() -> None:
    """Test that valid FSM storage types are accepted."""
    os.environ["TELEGRAM_TOKEN"] = "123456:test"
    valid_types = ["memory", "redis"]

    for storage_type in valid_types:
        settings = Settings(
            TELEGRAM_TOKEN="123456:test",
            FSM_STORAGE_TYPE=storage_type,
        )
        assert settings.FSM_STORAGE_TYPE == storage_type


@pytest.mark.unit
def test_converts_string_paths_to_path_objects() -> None:
    """Test that string paths are converted to Path objects."""
    os.environ["TELEGRAM_TOKEN"] = "123456:test"

    settings = Settings(
        TELEGRAM_TOKEN="123456:test",
        DATA_DIR="/tmp/data",
        SESSION_DIR="/tmp/sessions",
        LOG_DIR="/tmp/logs",
        ERROR_DIR="/tmp/errors",
    )

    assert isinstance(settings.DATA_DIR, Path)
    assert isinstance(settings.SESSION_DIR, Path)
    assert isinstance(settings.LOG_DIR, Path)
    assert isinstance(settings.ERROR_DIR, Path)

    assert settings.DATA_DIR == Path("/tmp/data")
    assert settings.SESSION_DIR == Path("/tmp/sessions")
    assert settings.LOG_DIR == Path("/tmp/logs")
    assert settings.ERROR_DIR == Path("/tmp/errors")


@pytest.mark.unit
def test_default_values() -> None:
    """Test that default values are set correctly."""
    os.environ["TELEGRAM_TOKEN"] = "123456:test"

    settings = Settings(TELEGRAM_TOKEN="123456:test")

    assert settings.DATABASE_URL == "sqlite+aiosqlite:///./bot.db"
    assert settings.LOG_LEVEL == "INFO"
    assert settings.DEBUG is False
    assert settings.FSM_STORAGE_TYPE == "memory"
    assert settings.PERMISSION_CACHE_TTL == 300
    assert settings.PLAYWRIGHT_HEADLESS is True
    assert settings.PLAYWRIGHT_TIMEOUT == 30000
    assert settings.WORKER_POLL_INTERVAL == 1.0
    assert settings.WORKER_RETRY_ATTEMPTS == 3
    assert settings.WORKER_RETRY_BACKOFF == "2,4,8"


@pytest.mark.unit
def test_get_settings_returns_settings_instance() -> None:
    """Test that get_settings() returns Settings instance."""
    os.environ["TELEGRAM_TOKEN"] = "123456:test"

    settings = get_settings()

    assert isinstance(settings, Settings)
    assert settings.TELEGRAM_TOKEN == "123456:test"
