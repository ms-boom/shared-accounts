"""Tests for exception hierarchy and message handling."""

import pytest

from core.exceptions import (
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

ALL_EXCEPTION_CLASSES = [
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


# --- Hierarchy ---


@pytest.mark.unit
def test__bot_error__is_base_exception() -> None:
    error = BotError("test error")
    assert isinstance(error, Exception)
    assert str(error) == "test error"


@pytest.mark.unit
@pytest.mark.parametrize(
    "exc_class",
    [cls for cls in ALL_EXCEPTION_CLASSES if cls is not BotError],
    ids=lambda c: c.__name__,
)
def test__exception__inherits_from_bot_error(exc_class) -> None:
    error = exc_class("some error")
    assert isinstance(error, BotError)
    assert isinstance(error, Exception)
    assert str(error) == "some error"


# --- Messages ---


@pytest.mark.unit
@pytest.mark.parametrize("exc_class", ALL_EXCEPTION_CLASSES, ids=lambda c: c.__name__)
def test__exception__preserves_message(exc_class) -> None:
    msg = "detailed error message"
    assert str(exc_class(msg)) == msg


@pytest.mark.unit
def test__exception__can_be_raised_and_caught() -> None:
    with pytest.raises(DatabaseError) as exc_info:
        raise DatabaseError("test database error")

    assert str(exc_info.value) == "test database error"
    assert isinstance(exc_info.value, BotError)


@pytest.mark.unit
def test__exception__catch_specific_type() -> None:
    with pytest.raises(UserNotFoundError, match="user 123 not found"):
        raise UserNotFoundError("user 123 not found")


@pytest.mark.unit
def test__exception__catch_via_base_class() -> None:
    with pytest.raises(BotError, match="task failed"):
        raise TaskError("task failed")
