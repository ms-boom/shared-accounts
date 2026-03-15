"""Tests for UserService."""

import pytest

from core.services.user_service import UserService


@pytest.mark.unit
async def test__registers_new_user(user_service: UserService) -> None:
    result = await user_service.register_user(
        user_id=123456789, username="testuser",
        first_name="Test", last_name="User", language_code="en",
    )

    assert result["id"] == 123456789
    assert result["username"] == "testuser"
    assert result["first_name"] == "Test"
    assert result["last_name"] == "User"
    assert result["language_code"] == "en"


@pytest.mark.unit
async def test__registers_user_with_minimal_fields(user_service: UserService) -> None:
    result = await user_service.register_user(
        user_id=987654321, username=None, first_name="Minimal",
    )

    assert result["id"] == 987654321
    assert result["first_name"] == "Minimal"
    assert result["username"] is None
    assert result["last_name"] is None
    assert result["language_code"] is None


@pytest.mark.unit
async def test__updates_existing_user_on_register(user_service: UserService) -> None:
    user_id = 123456789

    await user_service.register_user(
        user_id=user_id, username="testuser",
        first_name="Test", last_name="User", language_code="en",
    )

    result = await user_service.register_user(
        user_id=user_id, username="newusername",
        first_name="Updated", last_name="Name", language_code="ru",
    )

    assert result["first_name"] == "Updated"
    assert result["username"] == "newusername"
    assert result["language_code"] == "ru"


@pytest.mark.unit
async def test__gets_user_by_id(user_service: UserService) -> None:
    await user_service.register_user(
        user_id=123456789, username="testuser", first_name="Test",
    )

    result = await user_service.get_user(123456789)

    assert result is not None
    assert result["id"] == 123456789


@pytest.mark.unit
async def test__gets_user_returns_none_if_not_found(
    user_service: UserService,
) -> None:
    assert await user_service.get_user(999999999) is None


@pytest.mark.unit
async def test__handles_user_without_username(user_service: UserService) -> None:
    result = await user_service.register_user(
        user_id=111222333, username=None, first_name="NoUsername",
    )
    assert result["username"] is None


@pytest.mark.unit
async def test__handles_user_without_last_name(user_service: UserService) -> None:
    result = await user_service.register_user(
        user_id=444555666, username=None,
        first_name="OnlyFirstName", last_name=None,
    )
    assert result["last_name"] is None


@pytest.mark.unit
async def test__preserves_telegram_user_id(user_service: UserService) -> None:
    telegram_id = 123456789

    result = await user_service.register_user(
        user_id=telegram_id, username=None, first_name="Test",
    )
    assert result["id"] == telegram_id

    retrieved = await user_service.get_user(telegram_id)
    assert retrieved is not None
    assert retrieved["id"] == telegram_id


@pytest.mark.unit
async def test__register_multiple_users(user_service: UserService) -> None:
    r1 = await user_service.register_user(user_id=111, username=None, first_name="User1")
    r2 = await user_service.register_user(user_id=222, username=None, first_name="User2")
    r3 = await user_service.register_user(user_id=333, username=None, first_name="User3")

    assert r1["id"] == 111
    assert r2["id"] == 222
    assert r3["id"] == 333

    assert all([
        await user_service.get_user(111),
        await user_service.get_user(222),
        await user_service.get_user(333),
    ])


@pytest.mark.unit
async def test__updates_language_code(user_service: UserService) -> None:
    user_id = 123456

    await user_service.register_user(
        user_id=user_id, username=None, first_name="Test", language_code="en",
    )

    result = await user_service.register_user(
        user_id=user_id, username=None, first_name="Test", language_code="ru",
    )

    assert result["language_code"] == "ru"


@pytest.mark.unit
async def test__register_creates_timestamps(user_service: UserService) -> None:
    result = await user_service.register_user(
        user_id=123456789, username="testuser",
        first_name="Test", last_name="User", language_code="en",
    )

    assert result["created_at"] is not None
    assert result["updated_at"] is not None
