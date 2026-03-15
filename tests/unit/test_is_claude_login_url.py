"""Tests for ValidationService.is_claude_login_url().

The pattern must match both legacy login?token= and new magic-link URLs.
"""

import pytest

from core.services.validation_service import ValidationService


@pytest.mark.unit
def test__legacy_login_token__returns_true() -> None:
    assert ValidationService.is_claude_login_url(
        "https://claude.ai/login?token=abc123def456"
    )


@pytest.mark.unit
def test__magic_link_with_hash__returns_true() -> None:
    assert ValidationService.is_claude_login_url(
        "https://claude.ai/magic-link#some-token-value"
    )


@pytest.mark.unit
def test__magic_link_with_query__returns_true() -> None:
    assert ValidationService.is_claude_login_url(
        "https://claude.ai/magic-link?token=xyz789&other=param"
    )


@pytest.mark.unit
def test__magic_link_long_token__returns_true() -> None:
    token = "a" * 200
    assert ValidationService.is_claude_login_url(
        f"https://claude.ai/magic-link#{token}"
    )


@pytest.mark.unit
def test__empty_string__returns_false() -> None:
    assert ValidationService.is_claude_login_url("") is False


@pytest.mark.unit
def test__random_url__returns_false() -> None:
    assert ValidationService.is_claude_login_url("https://google.com") is False


@pytest.mark.unit
def test__claude_base_url__returns_false() -> None:
    assert ValidationService.is_claude_login_url("https://claude.ai/") is False


@pytest.mark.unit
def test__magic_link_no_content__returns_false() -> None:
    assert (
        ValidationService.is_claude_login_url("https://claude.ai/magic-link") is False
    )


@pytest.mark.unit
def test__login_without_token__returns_false() -> None:
    assert ValidationService.is_claude_login_url("https://claude.ai/login") is False


@pytest.mark.unit
def test__http_instead_of_https__returns_false() -> None:
    assert (
        ValidationService.is_claude_login_url("http://claude.ai/login?token=abc123")
        is False
    )


@pytest.mark.unit
def test__auth_url__returns_false() -> None:
    """Auth URLs should not be recognized as login URLs."""
    assert (
        ValidationService.is_claude_login_url(
            "https://claude.ai/auth/authorize?client_id=test"
        )
        is False
    )
