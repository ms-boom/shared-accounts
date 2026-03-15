"""Unit tests for ValidationService.

Covers email validation, Claude login URL patterns (including magic-link),
and Claude auth URL patterns (auth/authorize and login/authorize).
"""

import pytest

from core.services.validation_service import ValidationService


@pytest.mark.unit
class TestValidateEmail:
    """Tests for ValidationService.validate_email()."""

    @pytest.mark.parametrize(
        "email",
        [
            "test@example.com",
            "user.name@example.com",
            "user+tag@example.co.uk",
            "first.last@subdomain.example.com",
            "123@example.com",
            "user_name@example.com",
            "a@b.cd",
        ],
        ids=lambda e: e,
    )
    def test__validate_email__valid_formats__returns_true(self, email: str) -> None:
        assert ValidationService.validate_email(email) is True

    @pytest.mark.parametrize(
        "email",
        [
            "",
            "not-an-email",
            "@example.com",
            "user@",
            "user @example.com",
            "user@example",
            "user@example@com",
            "user name@example.com",
        ],
        ids=lambda e: e or "empty",
    )
    def test__validate_email__invalid_formats__returns_false(
        self, email: str
    ) -> None:
        assert ValidationService.validate_email(email) is False


@pytest.mark.unit
class TestIsClaudeLoginUrl:
    """Tests for ValidationService.is_claude_login_url().

    The pattern must match both legacy login?token= and new magic-link URLs.
    """

    def test__is_claude_login_url__legacy_login_token__returns_true(self) -> None:
        url = "https://claude.ai/login?token=abc123def456"
        assert ValidationService.is_claude_login_url(url) is True

    def test__is_claude_login_url__magic_link_with_hash__returns_true(self) -> None:
        url = "https://claude.ai/magic-link#some-token-value"
        assert ValidationService.is_claude_login_url(url) is True

    def test__is_claude_login_url__magic_link_with_query__returns_true(self) -> None:
        url = "https://claude.ai/magic-link?token=xyz789&other=param"
        assert ValidationService.is_claude_login_url(url) is True

    def test__is_claude_login_url__magic_link_long_token__returns_true(self) -> None:
        token = "a" * 200
        url = f"https://claude.ai/magic-link#{token}"
        assert ValidationService.is_claude_login_url(url) is True

    def test__is_claude_login_url__empty_string__returns_false(self) -> None:
        assert ValidationService.is_claude_login_url("") is False

    def test__is_claude_login_url__random_url__returns_false(self) -> None:
        assert ValidationService.is_claude_login_url("https://google.com") is False

    def test__is_claude_login_url__claude_base_url__returns_false(self) -> None:
        assert ValidationService.is_claude_login_url("https://claude.ai/") is False

    def test__is_claude_login_url__magic_link_no_content__returns_false(self) -> None:
        """magic-link without # or ? followed by content must be rejected."""
        assert ValidationService.is_claude_login_url("https://claude.ai/magic-link") is False

    def test__is_claude_login_url__login_without_token__returns_false(self) -> None:
        """login without ?token= should not match."""
        assert ValidationService.is_claude_login_url("https://claude.ai/login") is False

    def test__is_claude_login_url__http_instead_of_https__returns_false(self) -> None:
        url = "http://claude.ai/login?token=abc123"
        assert ValidationService.is_claude_login_url(url) is False

    def test__is_claude_login_url__auth_url__returns_false(self) -> None:
        """Auth URLs should not be recognized as login URLs."""
        url = "https://claude.ai/auth/authorize?client_id=test"
        assert ValidationService.is_claude_login_url(url) is False


@pytest.mark.unit
class TestIsClaudeAuthUrl:
    """Tests for ValidationService.is_claude_auth_url().

    The pattern must match both auth/authorize and login/authorize paths.
    """

    def test__is_claude_auth_url__auth_authorize__returns_true(self) -> None:
        url = "https://claude.ai/auth/authorize?client_id=test&scope=read"
        assert ValidationService.is_claude_auth_url(url) is True

    def test__is_claude_auth_url__login_authorize__returns_true(self) -> None:
        url = "https://claude.ai/login/authorize?client_id=test"
        assert ValidationService.is_claude_auth_url(url) is True

    def test__is_claude_auth_url__empty_string__returns_false(self) -> None:
        assert ValidationService.is_claude_auth_url("") is False

    def test__is_claude_auth_url__random_url__returns_false(self) -> None:
        assert ValidationService.is_claude_auth_url("https://google.com") is False

    def test__is_claude_auth_url__login_url__returns_false(self) -> None:
        """Login URLs should not be recognized as auth URLs."""
        url = "https://claude.ai/login?token=abc123"
        assert ValidationService.is_claude_auth_url(url) is False

    def test__is_claude_auth_url__no_query_params__returns_false(self) -> None:
        """auth/authorize without query string must be rejected."""
        url = "https://claude.ai/auth/authorize"
        assert ValidationService.is_claude_auth_url(url) is False

    def test__is_claude_auth_url__http_instead_of_https__returns_false(self) -> None:
        url = "http://claude.ai/auth/authorize?client_id=test"
        assert ValidationService.is_claude_auth_url(url) is False
