"""Unit tests for exception message handling in bot/core/exceptions.py."""

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
def test_exceptions_preserve_message() -> None:
    """Test that all exceptions preserve error messages."""
    test_message = "detailed error message"

    exceptions_to_test = [
        BotError,
        ConfigurationError,
        DatabaseError,
        PermissionError,
        GroupNotFoundError,
        UserNotFoundError,
        BrowserError,
        SessionError,
        TaskError,
    ]

    for exception_class in exceptions_to_test:
        error = exception_class(test_message)
        assert str(error) == test_message


@pytest.mark.unit
def test_exceptions_can_be_raised_and_caught() -> None:
    """Test that exceptions can be raised and caught properly."""
    with pytest.raises(DatabaseError) as exc_info:
        raise DatabaseError("test database error")

    assert str(exc_info.value) == "test database error"
    assert isinstance(exc_info.value, BotError)


@pytest.mark.unit
def test_can_catch_specific_exception() -> None:
    """Test catching specific exception type."""
    caught = False

    try:
        raise UserNotFoundError("user 123 not found")
    except UserNotFoundError as e:
        caught = True
        assert str(e) == "user 123 not found"

    assert caught


@pytest.mark.unit
def test_can_catch_base_exception() -> None:
    """Test catching exception via base class."""
    caught = False

    try:
        raise TaskError("task failed")
    except BotError as e:
        caught = True
        assert str(e) == "task failed"

    assert caught
