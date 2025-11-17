"""Unit tests for exception class hierarchy in bot/core/exceptions.py."""

import pytest

from bot.core.exceptions import (
    BotError,
    BrowserError,
    ConfigurationError,
    DatabaseError,
    GroupNotFoundError,
    PermissionError,
    SessionError,
    TaskError,
    UserNotFoundError,
)


@pytest.mark.unit
def test_bot_error_is_base_exception() -> None:
    """Test that BotError is base for all bot exceptions."""
    error = BotError("test error")

    assert isinstance(error, Exception)
    assert str(error) == "test error"


@pytest.mark.unit
def test_configuration_error_inherits_from_bot_error() -> None:
    """Test that ConfigurationError inherits from BotError."""
    error = ConfigurationError("config error")

    assert isinstance(error, BotError)
    assert isinstance(error, Exception)
    assert str(error) == "config error"


@pytest.mark.unit
def test_database_error_inherits_from_bot_error() -> None:
    """Test that DatabaseError inherits from BotError."""
    error = DatabaseError("database error")

    assert isinstance(error, BotError)
    assert isinstance(error, Exception)
    assert str(error) == "database error"


@pytest.mark.unit
def test_permission_error_inherits_from_bot_error() -> None:
    """Test that PermissionError inherits from BotError."""
    error = PermissionError("permission denied")

    assert isinstance(error, BotError)
    assert isinstance(error, Exception)
    assert str(error) == "permission denied"


@pytest.mark.unit
def test_group_not_found_error_inherits_from_bot_error() -> None:
    """Test that GroupNotFoundError inherits from BotError."""
    error = GroupNotFoundError("group not found")

    assert isinstance(error, BotError)
    assert isinstance(error, Exception)
    assert str(error) == "group not found"


@pytest.mark.unit
def test_user_not_found_error_inherits_from_bot_error() -> None:
    """Test that UserNotFoundError inherits from BotError."""
    error = UserNotFoundError("user not found")

    assert isinstance(error, BotError)
    assert isinstance(error, Exception)
    assert str(error) == "user not found"


@pytest.mark.unit
def test_browser_error_inherits_from_bot_error() -> None:
    """Test that BrowserError inherits from BotError."""
    error = BrowserError("browser error")

    assert isinstance(error, BotError)
    assert isinstance(error, Exception)
    assert str(error) == "browser error"


@pytest.mark.unit
def test_session_error_inherits_from_bot_error() -> None:
    """Test that SessionError inherits from BotError."""
    error = SessionError("session error")

    assert isinstance(error, BotError)
    assert isinstance(error, Exception)
    assert str(error) == "session error"


@pytest.mark.unit
def test_task_error_inherits_from_bot_error() -> None:
    """Test that TaskError inherits from BotError."""
    error = TaskError("task error")

    assert isinstance(error, BotError)
    assert isinstance(error, Exception)
    assert str(error) == "task error"
