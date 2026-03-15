"""Tests for ValidationService.is_claude_auth_url().

The pattern must match auth/authorize, login/authorize, and oauth/authorize paths.
"""

import pytest

from core.services.validation_service import ValidationService


@pytest.mark.unit
def test__auth_authorize__returns_true() -> None:
    assert ValidationService.is_claude_auth_url(
        "https://claude.ai/auth/authorize?client_id=test&scope=read"
    )


@pytest.mark.unit
def test__login_authorize__returns_true() -> None:
    assert ValidationService.is_claude_auth_url(
        "https://claude.ai/login/authorize?client_id=test"
    )


@pytest.mark.unit
def test__oauth_authorize__returns_true() -> None:
    assert ValidationService.is_claude_auth_url(
        "https://claude.ai/oauth/authorize?code=true&client_id=9d1c250a"
    )


@pytest.mark.unit
def test__empty_string__returns_false() -> None:
    assert ValidationService.is_claude_auth_url("") is False


@pytest.mark.unit
def test__random_url__returns_false() -> None:
    assert ValidationService.is_claude_auth_url("https://google.com") is False


@pytest.mark.unit
def test__login_url__returns_false() -> None:
    """Login URLs should not be recognized as auth URLs."""
    assert (
        ValidationService.is_claude_auth_url(
            "https://claude.ai/login?token=abc123"
        )
        is False
    )


@pytest.mark.unit
def test__no_query_params__returns_false() -> None:
    assert (
        ValidationService.is_claude_auth_url("https://claude.ai/auth/authorize")
        is False
    )


@pytest.mark.unit
def test__http_instead_of_https__returns_false() -> None:
    assert (
        ValidationService.is_claude_auth_url(
            "http://claude.ai/auth/authorize?client_id=test"
        )
        is False
    )
