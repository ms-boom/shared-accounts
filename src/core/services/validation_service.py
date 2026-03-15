"""Validation service for emails and URLs."""

import re


class ValidationService:
    """Service for validating user input."""

    # Email validation regex
    EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

    # Claude URL patterns
    CLAUDE_LOGIN_URL_PATTERN = re.compile(r"https://claude\.ai/login\?token=.+")
    CLAUDE_AUTH_URL_PATTERN = re.compile(
        r"https://claude\.ai/(auth/authorize|login/authorize)\?.+"
    )

    @classmethod
    def validate_email(cls, email: str) -> bool:
        """
        Validate email format.

        Args:
            email: Email address to validate

        Returns:
            True if email format is valid, False otherwise
        """
        return bool(cls.EMAIL_REGEX.match(email))

    @classmethod
    def is_claude_login_url(cls, url: str) -> bool:
        """
        Check if URL is a Claude login link.

        Args:
            url: URL to check

        Returns:
            True if URL is Claude login link, False otherwise
        """
        return bool(cls.CLAUDE_LOGIN_URL_PATTERN.match(url))

    @classmethod
    def is_claude_auth_url(cls, url: str) -> bool:
        """
        Check if URL is a Claude authorization URL.

        Args:
            url: URL to check

        Returns:
            True if URL is Claude authorization URL, False otherwise
        """
        return bool(cls.CLAUDE_AUTH_URL_PATTERN.match(url))
