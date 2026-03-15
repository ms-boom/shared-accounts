"""Tests for UserRepository."""

import pytest

from core.db.repositories.user_repository import UserRepository
from core.exceptions import UserNotFoundError


@pytest.mark.unit
async def test__creates_user(user_repository: UserRepository) -> None:
    user = await user_repository.create(
        user_id=123456789, username="testuser", first_name="Test",
    )

    assert user["id"] == 123456789
    assert user["username"] == "testuser"
    assert user["first_name"] == "Test"
    assert user["last_name"] is None
    assert user["language_code"] is None
    assert user["created_at"] is not None
    assert user["updated_at"] is not None


@pytest.mark.unit
async def test__creates_user_with_all_fields(user_repository: UserRepository) -> None:
    user = await user_repository.create(
        user_id=123456789, username="testuser",
        first_name="Test", last_name="User", language_code="en",
    )

    assert user["last_name"] == "User"
    assert user["language_code"] == "en"


@pytest.mark.unit
async def test__gets_user_by_id(user_repository: UserRepository) -> None:
    await user_repository.create(
        user_id=123456789, username="testuser", first_name="Test",
    )

    user = await user_repository.get_by_id(123456789)

    assert user is not None
    assert user["id"] == 123456789
    assert user["username"] == "testuser"


@pytest.mark.unit
async def test__gets_user_returns_none_if_not_found(
    user_repository: UserRepository,
) -> None:
    assert await user_repository.get_by_id(999999999) is None


@pytest.mark.unit
async def test__updates_user(user_repository: UserRepository) -> None:
    await user_repository.create(
        user_id=123456789, username="oldusername", first_name="Old",
    )

    updated = await user_repository.update(
        user_id=123456789, username="newusername", first_name="New",
    )

    assert updated["username"] == "newusername"
    assert updated["first_name"] == "New"


@pytest.mark.unit
async def test__updates_user_partially(user_repository: UserRepository) -> None:
    await user_repository.create(
        user_id=123456789, username="testuser",
        first_name="Test", last_name="User",
    )

    updated = await user_repository.update(user_id=123456789, username="newusername")

    assert updated["username"] == "newusername"
    assert updated["first_name"] == "Test"
    assert updated["last_name"] == "User"


@pytest.mark.unit
async def test__update_raises_error_if_not_found(
    user_repository: UserRepository,
) -> None:
    with pytest.raises(UserNotFoundError, match="User 999999999 not found"):
        await user_repository.update(user_id=999999999, username="newusername")


@pytest.mark.unit
async def test__update_with_no_changes_returns_existing(
    user_repository: UserRepository,
) -> None:
    original = await user_repository.create(
        user_id=123456789, username="testuser", first_name="Test",
    )

    updated = await user_repository.update(user_id=123456789)

    assert updated["username"] == original["username"]
    assert updated["first_name"] == original["first_name"]


@pytest.mark.unit
async def test__creates_multiple_users(user_repository: UserRepository) -> None:
    user1 = await user_repository.create(user_id=111, username="user1", first_name="User1")
    user2 = await user_repository.create(user_id=222, username="user2", first_name="User2")

    assert user1["id"] == 111
    assert user2["id"] == 222

    assert await user_repository.get_by_id(111) is not None
    assert await user_repository.get_by_id(222) is not None


@pytest.mark.unit
async def test__updates_updated_at_timestamp(user_repository: UserRepository) -> None:
    await user_repository.create(
        user_id=123456789, username="testuser", first_name="Test",
    )

    updated = await user_repository.update(user_id=123456789, username="newusername")
    assert updated["updated_at"] is not None
