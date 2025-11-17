"""Custom exceptions for the bot application."""


class BotError(Exception):
    """Base exception for all bot errors."""

    pass


class ConfigurationError(BotError):
    """Raised when configuration is invalid or missing."""

    pass


class DatabaseError(BotError):
    """Raised when database operations fail."""

    pass


class PermissionError(BotError):
    """Raised when user doesn't have required permissions."""

    pass


class GroupNotFoundError(BotError):
    """Raised when a group is not found in the database."""

    pass


class UserNotFoundError(BotError):
    """Raised when a user is not found in the database."""

    pass
