"""Unit tests for bot/core/exceptions.py."""

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


@pytest.mark.unit
class TestExceptionHierarchy:
    """Tests for exception class hierarchy."""

    def test_bot_error_is_base_exception(self) -> None:
        """Test that BotError is base for all bot exceptions."""
        error = BotError("test error")

        assert isinstance(error, Exception)
        assert str(error) == "test error"

    def test_configuration_error_inherits_from_bot_error(self) -> None:
        """Test that ConfigurationError inherits from BotError."""
        error = ConfigurationError("config error")

        assert isinstance(error, BotError)
        assert isinstance(error, Exception)
        assert str(error) == "config error"

    def test_database_error_inherits_from_bot_error(self) -> None:
        """Test that DatabaseError inherits from BotError."""
        error = DatabaseError("database error")

        assert isinstance(error, BotError)
        assert isinstance(error, Exception)
        assert str(error) == "database error"

    def test_permission_error_inherits_from_bot_error(self) -> None:
        """Test that PermissionError inherits from BotError."""
        error = PermissionError("permission denied")

        assert isinstance(error, BotError)
        assert isinstance(error, Exception)
        assert str(error) == "permission denied"

    def test_group_not_found_error_inherits_from_bot_error(self) -> None:
        """Test that GroupNotFoundError inherits from BotError."""
        error = GroupNotFoundError("group not found")

        assert isinstance(error, BotError)
        assert isinstance(error, Exception)
        assert str(error) == "group not found"

    def test_user_not_found_error_inherits_from_bot_error(self) -> None:
        """Test that UserNotFoundError inherits from BotError."""
        error = UserNotFoundError("user not found")

        assert isinstance(error, BotError)
        assert isinstance(error, Exception)
        assert str(error) == "user not found"

    def test_browser_error_inherits_from_bot_error(self) -> None:
        """Test that BrowserError inherits from BotError."""
        error = BrowserError("browser error")

        assert isinstance(error, BotError)
        assert isinstance(error, Exception)
        assert str(error) == "browser error"

    def test_session_error_inherits_from_bot_error(self) -> None:
        """Test that SessionError inherits from BotError."""
        error = SessionError("session error")

        assert isinstance(error, BotError)
        assert isinstance(error, Exception)
        assert str(error) == "session error"

    def test_task_error_inherits_from_bot_error(self) -> None:
        """Test that TaskError inherits from BotError."""
        error = TaskError("task error")

        assert isinstance(error, BotError)
        assert isinstance(error, Exception)
        assert str(error) == "task error"


@pytest.mark.unit
class TestExceptionMessages:
    """Tests for exception message handling."""

    def test_exceptions_preserve_message(self) -> None:
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

    def test_exceptions_can_be_raised_and_caught(self) -> None:
        """Test that exceptions can be raised and caught properly."""
        with pytest.raises(DatabaseError) as exc_info:
            raise DatabaseError("test database error")

        assert str(exc_info.value) == "test database error"
        assert isinstance(exc_info.value, BotError)

    def test_can_catch_specific_exception(self) -> None:
        """Test catching specific exception type."""
        caught = False

        try:
            raise UserNotFoundError("user 123 not found")
        except UserNotFoundError as e:
            caught = True
            assert str(e) == "user 123 not found"

        assert caught

    def test_can_catch_base_exception(self) -> None:
        """Test catching exception via base class."""
        caught = False

        try:
            raise TaskError("task failed")
        except BotError as e:
            caught = True
            assert str(e) == "task failed"

        assert caught
