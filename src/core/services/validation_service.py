"""Validation service for emails and URLs."""

import re


class ValidationService:
    """Service for validating user input."""

    # Email validation regex
    EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

    # Claude URL patterns
    CLAUDE_LOGIN_URL_PATTERN = re.compile(
        r"https://claude\.ai/(login\?token=|magic-link[#?]).+"
    )
    # Any http(s) URL token, used to isolate a URL from surrounding text.
    URL_TOKEN_PATTERN = re.compile(r"https?://\S+")
    # Punctuation that commonly clings to a pasted URL and is not part of it.
    # ':' is excluded — the magic-link token contains it internally.
    _URL_TRAILING_PUNCTUATION = ".,;!?)]}>\"'`»«"
    CLAUDE_AUTH_URL_PATTERN = re.compile(
        r"https://claude\.ai/(auth/authorize|login/authorize|oauth/authorize)\?.+"
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
    def extract_claude_login_url(cls, text: str) -> str | None:
        """
        Find a Claude login URL anywhere in a message and return it.

        Users are asked to send the single-use magic link wrapped in
        `code` / ```code block``` so Telegram does not linkify it and burn
        the token before the bot opens it. Telegram drops the backticks from
        message.text, so the URL arrives as plain text — possibly with
        surrounding words, newlines, or clinging punctuation. Isolate each
        URL token, trim clinging punctuation, and defer to
        is_claude_login_url() for what counts as a login link.

        Args:
            text: Raw message text to search

        Returns:
            The first Claude login URL found, or None if there is none
        """
        for match in cls.URL_TOKEN_PATTERN.finditer(text):
            url = match.group(0).rstrip(cls._URL_TRAILING_PUNCTUATION)
            if cls.is_claude_login_url(url):
                return url
        return None

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
