"""Unit tests for validate_email() function in bot/handlers/claude_auth.py."""

import pytest

from bot.handlers.claude_auth import validate_email


@pytest.mark.unit
def test_valid_email_formats() -> None:
    """Test validate_email accepts valid email formats."""
    valid_emails = [
        "test@example.com",
        "user.name@example.com",
        "user+tag@example.co.uk",
        "first.last@subdomain.example.com",
        "123@example.com",
        "user_name@example.com",
    ]

    for email in valid_emails:
        assert validate_email(email), f"Should accept {email}"


@pytest.mark.unit
def test_invalid_email_formats() -> None:
    """Test validate_email rejects invalid email formats."""
    invalid_emails = [
        "",
        "not-an-email",
        "@example.com",
        "user@",
        "user @example.com",  # Space
        "user@example",  # No TLD
    ]

    for email in invalid_emails:
        assert not validate_email(email), f"Should reject {email}"


@pytest.mark.unit
def test_email_with_special_characters() -> None:
    """Test validate_email handles special characters."""
    # Valid special characters
    assert validate_email("user+filter@example.com")
    assert validate_email("user.name@example.com")
    assert validate_email("user_name@example.com")

    # Invalid special characters
    assert not validate_email("user@example@com")
    assert not validate_email("user name@example.com")
