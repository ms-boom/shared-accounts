"""Tests for validate_email() — backward-compat wrapper over ValidationService."""

import pytest

from core.services.validation_service import ValidationService

validate_email = ValidationService.validate_email


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
        "user+filter@example.com",
    ],
    ids=lambda e: e,
)
def test__validate_email__valid_formats__returns_true(email: str) -> None:
    assert validate_email(email) is True


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
    assert validate_email(email) is False
