"""Tests for Settings configuration class."""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from core.config import Settings, get_settings


@pytest.mark.unit
def test__settings__creates_with_valid_token(temp_dir: Path) -> None:
    os.environ["TELEGRAM_TOKEN"] = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"

    settings = Settings(
        TELEGRAM_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        DATA_DIR=temp_dir,
    )

    assert settings.TELEGRAM_TOKEN == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    assert settings.DEBUG is False
    assert settings.LOG_LEVEL == "INFO"


@pytest.mark.unit
def test__settings__validates_token_not_empty() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(TELEGRAM_TOKEN="")

    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert "TELEGRAM_TOKEN is required" in str(errors[0]["ctx"]["error"])


@pytest.mark.unit
def test__settings__validates_token_not_whitespace() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(TELEGRAM_TOKEN="   ")

    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert "TELEGRAM_TOKEN is required" in str(errors[0]["ctx"]["error"])


@pytest.mark.unit
def test__settings__strips_token_whitespace() -> None:
    os.environ["TELEGRAM_TOKEN"] = "  123456:test  "
    settings = Settings(TELEGRAM_TOKEN="  123456:test  ")
    assert settings.TELEGRAM_TOKEN == "123456:test"


@pytest.mark.unit
def test__settings__validates_log_level() -> None:
    os.environ["TELEGRAM_TOKEN"] = "123456:test"

    with pytest.raises(ValidationError) as exc_info:
        Settings(TELEGRAM_TOKEN="123456:test", LOG_LEVEL="INVALID")

    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert "LOG_LEVEL must be one of" in str(errors[0]["ctx"]["error"])


@pytest.mark.unit
def test__settings__converts_log_level_to_uppercase() -> None:
    os.environ["TELEGRAM_TOKEN"] = "123456:test"
    settings = Settings(TELEGRAM_TOKEN="123456:test", LOG_LEVEL="debug")
    assert settings.LOG_LEVEL == "DEBUG"


@pytest.mark.unit
@pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
def test__settings__accepts_valid_log_levels(level: str) -> None:
    os.environ["TELEGRAM_TOKEN"] = "123456:test"
    settings = Settings(TELEGRAM_TOKEN="123456:test", LOG_LEVEL=level)
    assert settings.LOG_LEVEL == level


@pytest.mark.unit
def test__settings__converts_string_paths_to_path_objects() -> None:
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


@pytest.mark.unit
def test__settings__default_values() -> None:
    os.environ["TELEGRAM_TOKEN"] = "123456:test"
    os.environ.pop("DATABASE_URL", None)

    settings = Settings(TELEGRAM_TOKEN="123456:test")

    assert settings.DATABASE_URL == "sqlite+aiosqlite:////data/claude_bot.db"
    assert settings.LOG_LEVEL == "INFO"
    assert settings.DEBUG is False
    assert settings.PERMISSION_CACHE_TTL == 300
    assert settings.PLAYWRIGHT_HEADLESS is True
    assert settings.PLAYWRIGHT_TIMEOUT == 30000
    assert settings.WORKER_POLL_INTERVAL == 1.0
    assert settings.WORKER_RETRY_ATTEMPTS == 3
    assert settings.WORKER_RETRY_BACKOFF == "2,4,8"


@pytest.mark.unit
def test__get_settings__returns_settings_instance() -> None:
    os.environ["TELEGRAM_TOKEN"] = "123456:test"
    settings = get_settings()
    assert isinstance(settings, Settings)
    assert settings.TELEGRAM_TOKEN == "123456:test"


@pytest.mark.unit
def test__settings__default_fingerprint_profile() -> None:
    os.environ["TELEGRAM_TOKEN"] = "123456:test"
    for key in (
        "DEFAULT_USER_AGENT",
        "DEFAULT_CPU_CORES",
        "DEFAULT_DEVICE_MEMORY",
        "DEFAULT_TIMEZONE",
        "DEFAULT_LOCALE",
    ):
        os.environ.pop(key, None)

    settings = Settings(TELEGRAM_TOKEN="123456:test")

    assert settings.DEFAULT_USER_AGENT == (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
    )
    assert settings.DEFAULT_CPU_CORES == 8
    assert settings.DEFAULT_DEVICE_MEMORY == 8
    assert settings.DEFAULT_TIMEZONE == "America/New_York"
    assert settings.DEFAULT_LOCALE == "en-US"


@pytest.mark.unit
def test__settings__rejects_invalid_default_device_memory() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(TELEGRAM_TOKEN="123456:test", DEFAULT_DEVICE_MEMORY=3)

    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert "Device memory" in str(errors[0]["ctx"]["error"])


@pytest.mark.unit
def test__settings__rejects_invalid_default_cpu_cores() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(TELEGRAM_TOKEN="123456:test", DEFAULT_CPU_CORES=64)

    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert "CPU cores" in str(errors[0]["ctx"]["error"])


@pytest.mark.unit
def test__settings__rejects_invalid_default_timezone() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(TELEGRAM_TOKEN="123456:test", DEFAULT_TIMEZONE="Mars/Olympus_Mons")

    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert "Unknown IANA timezone" in str(errors[0]["ctx"]["error"])


@pytest.mark.unit
def test__settings__rejects_invalid_default_locale() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(TELEGRAM_TOKEN="123456:test", DEFAULT_LOCALE="EN_us")

    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert "Locale" in str(errors[0]["ctx"]["error"])


@pytest.mark.unit
def test__settings__rejects_empty_default_user_agent() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(TELEGRAM_TOKEN="123456:test", DEFAULT_USER_AGENT="   ")

    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert "User-Agent" in str(errors[0]["ctx"]["error"])
