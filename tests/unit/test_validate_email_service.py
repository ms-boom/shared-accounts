"""Tests for ValidationService.validate_email()."""

import pytest

from core.services.validation_service import ValidationService


@pytest.mark.unit
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
def test__validate_email__valid_formats__returns_true(email: str) -> None:
    assert ValidationService.validate_email(email) is True


@pytest.mark.unit
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
def test__validate_email__invalid_formats__returns_false(email: str) -> None:
    assert ValidationService.validate_email(email) is False
