"""Unit tests for bot/services/user_service.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import User
from databases import Database as DatabasesDatabase

from bot.db.database import Database
from bot.db.repositories.user_repository import UserRepository
from bot.services.user_service import UserService


@pytest.mark.unit
class TestUserService:
    """Tests for UserService class."""

    @pytest.fixture
    async def user_service_with_real_db(
        self, test_database: DatabasesDatabase
    ) -> UserService:
        """
        Create UserService with real database for integration-like tests.

        Args:
            test_database: Test database fixture

        Returns:
            UserService instance
        """
        mock_db = MagicMock(spec=Database)
        mock_db.get_connection.return_value = test_database

        return UserService(mock_db)

    @pytest.fixture
    def telegram_user_full(self) -> User:
        """
        Create Telegram user with all fields.

        Returns:
            User instance with all fields populated
        """
        return User(
            id=123456789,
            is_bot=False,
            first_name="Test",
            last_name="User",
            username="testuser",
            language_code="en",
        )

    @pytest.fixture
    def telegram_user_minimal(self) -> User:
        """
        Create Telegram user with minimal fields.

        Returns:
            User instance with only required fields
        """
        return User(
            id=987654321,
            is_bot=False,
            first_name="Minimal",
        )

    async def test_registers_new_user(
        self,
        user_service_with_real_db: UserService,
        telegram_user_full: User,
    ) -> None:
        """Test registering a new user."""
        result = await user_service_with_real_db.register_user(telegram_user_full)

        assert result["id"] == telegram_user_full.id
        assert result["username"] == telegram_user_full.username
        assert result["first_name"] == telegram_user_full.first_name
        assert result["last_name"] == telegram_user_full.last_name
        assert result["language_code"] == telegram_user_full.language_code

    async def test_registers_user_with_minimal_fields(
        self,
        user_service_with_real_db: UserService,
        telegram_user_minimal: User,
    ) -> None:
        """Test registering user with minimal required fields."""
        result = await user_service_with_real_db.register_user(telegram_user_minimal)

        assert result["id"] == telegram_user_minimal.id
        assert result["first_name"] == telegram_user_minimal.first_name
        assert result["username"] is None
        assert result["last_name"] is None
        assert result["language_code"] is None

    async def test_updates_existing_user_on_register(
        self,
        user_service_with_real_db: UserService,
        telegram_user_full: User,
    ) -> None:
        """Test that registering existing user updates their info."""
        # Register user first
        await user_service_with_real_db.register_user(telegram_user_full)

        # Create updated user with same ID
        updated_user = User(
            id=telegram_user_full.id,
            is_bot=False,
            first_name="Updated",
            last_name="Name",
            username="newusername",
            language_code="ru",
        )

        # Register again - should update
        result = await user_service_with_real_db.register_user(updated_user)

        assert result["first_name"] == "Updated"
        assert result["last_name"] == "Name"
        assert result["username"] == "newusername"
        assert result["language_code"] == "ru"

    async def test_gets_user_by_id(
        self,
        user_service_with_real_db: UserService,
        telegram_user_full: User,
    ) -> None:
        """Test retrieving user by ID."""
        # Register user first
        await user_service_with_real_db.register_user(telegram_user_full)

        # Get user
        result = await user_service_with_real_db.get_user(telegram_user_full.id)

        assert result is not None
        assert result["id"] == telegram_user_full.id
        assert result["username"] == telegram_user_full.username

    async def test_gets_user_returns_none_if_not_found(
        self,
        user_service_with_real_db: UserService,
    ) -> None:
        """Test that get_user returns None for non-existent user."""
        result = await user_service_with_real_db.get_user(999999999)

        assert result is None

    async def test_handles_user_without_username(
        self,
        user_service_with_real_db: UserService,
    ) -> None:
        """Test handling users without username."""
        user = User(
            id=111222333,
            is_bot=False,
            first_name="NoUsername",
            username=None,
        )

        result = await user_service_with_real_db.register_user(user)

        assert result["username"] is None
        assert result["first_name"] == "NoUsername"

    async def test_handles_user_without_last_name(
        self,
        user_service_with_real_db: UserService,
    ) -> None:
        """Test handling users without last name."""
        user = User(
            id=444555666,
            is_bot=False,
            first_name="OnlyFirstName",
            last_name=None,
        )

        result = await user_service_with_real_db.register_user(user)

        assert result["last_name"] is None
        assert result["first_name"] == "OnlyFirstName"

    async def test_preserves_user_id_from_telegram(
        self,
        user_service_with_real_db: UserService,
    ) -> None:
        """Test that Telegram user_id is preserved exactly."""
        telegram_id = 123456789

        user = User(
            id=telegram_id,
            is_bot=False,
            first_name="Test",
        )

        result = await user_service_with_real_db.register_user(user)

        assert result["id"] == telegram_id

        # Verify via get_user
        retrieved = await user_service_with_real_db.get_user(telegram_id)
        assert retrieved is not None
        assert retrieved["id"] == telegram_id

    async def test_register_multiple_users(
        self,
        user_service_with_real_db: UserService,
    ) -> None:
        """Test registering multiple different users."""
        user1 = User(id=111, is_bot=False, first_name="User1")
        user2 = User(id=222, is_bot=False, first_name="User2")
        user3 = User(id=333, is_bot=False, first_name="User3")

        result1 = await user_service_with_real_db.register_user(user1)
        result2 = await user_service_with_real_db.register_user(user2)
        result3 = await user_service_with_real_db.register_user(user3)

        assert result1["id"] == 111
        assert result2["id"] == 222
        assert result3["id"] == 333

        # Verify all can be retrieved
        retrieved1 = await user_service_with_real_db.get_user(111)
        retrieved2 = await user_service_with_real_db.get_user(222)
        retrieved3 = await user_service_with_real_db.get_user(333)

        assert all([retrieved1, retrieved2, retrieved3])

    async def test_updates_language_code(
        self,
        user_service_with_real_db: UserService,
    ) -> None:
        """Test updating user language code."""
        # Register with English
        user = User(
            id=123456,
            is_bot=False,
            first_name="Test",
            language_code="en",
        )

        await user_service_with_real_db.register_user(user)

        # Update to Russian
        updated_user = User(
            id=123456,
            is_bot=False,
            first_name="Test",
            language_code="ru",
        )

        result = await user_service_with_real_db.register_user(updated_user)

        assert result["language_code"] == "ru"

    async def test_register_creates_timestamps(
        self,
        user_service_with_real_db: UserService,
        telegram_user_full: User,
    ) -> None:
        """Test that registration creates timestamps."""
        result = await user_service_with_real_db.register_user(telegram_user_full)

        assert "created_at" in result
        assert "updated_at" in result
        assert result["created_at"] is not None
        assert result["updated_at"] is not None
