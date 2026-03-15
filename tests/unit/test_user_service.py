"""Unit tests for core/services/user_service.py."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.db.database import Database
from core.services.user_service import UserService


@pytest.mark.unit
class TestUserService:
    """Tests for UserService class."""

    @pytest.fixture
    def user_service_with_real_db(
        self, db_sessionmaker: async_sessionmaker[AsyncSession]
    ) -> UserService:
        """
        Create UserService with real database for integration-like tests.

        Args:
            db_sessionmaker: Test session factory bound to test transaction

        Returns:
            UserService instance
        """

        async def _write(fn):  # noqa: ANN001
            async with db_sessionmaker() as session, session.begin():
                return await fn(session)

        mock_db = MagicMock(spec=Database)
        mock_db.session_maker = db_sessionmaker
        mock_db.write = AsyncMock(side_effect=_write)
        mock_db.read = db_sessionmaker

        return UserService(mock_db)

    async def test_registers_new_user(
        self,
        user_service_with_real_db: UserService,
    ) -> None:
        """Test registering a new user."""
        result = await user_service_with_real_db.register_user(
            user_id=123456789,
            username="testuser",
            first_name="Test",
            last_name="User",
            language_code="en",
        )

        assert result["id"] == 123456789
        assert result["username"] == "testuser"
        assert result["first_name"] == "Test"
        assert result["last_name"] == "User"
        assert result["language_code"] == "en"

    async def test_registers_user_with_minimal_fields(
        self,
        user_service_with_real_db: UserService,
    ) -> None:
        """Test registering user with minimal required fields."""
        result = await user_service_with_real_db.register_user(
            user_id=987654321,
            username=None,
            first_name="Minimal",
        )

        assert result["id"] == 987654321
        assert result["first_name"] == "Minimal"
        assert result["username"] is None
        assert result["last_name"] is None
        assert result["language_code"] is None

    async def test_updates_existing_user_on_register(
        self,
        user_service_with_real_db: UserService,
    ) -> None:
        """Test that registering existing user updates their info."""
        user_id = 123456789

        # Register user first
        await user_service_with_real_db.register_user(
            user_id=user_id,
            username="testuser",
            first_name="Test",
            last_name="User",
            language_code="en",
        )

        # Register again with updated info - should update
        result = await user_service_with_real_db.register_user(
            user_id=user_id,
            username="newusername",
            first_name="Updated",
            last_name="Name",
            language_code="ru",
        )

        assert result["first_name"] == "Updated"
        assert result["last_name"] == "Name"
        assert result["username"] == "newusername"
        assert result["language_code"] == "ru"

    async def test_gets_user_by_id(
        self,
        user_service_with_real_db: UserService,
    ) -> None:
        """Test retrieving user by ID."""
        user_id = 123456789

        # Register user first
        await user_service_with_real_db.register_user(
            user_id=user_id,
            username="testuser",
            first_name="Test",
        )

        # Get user
        result = await user_service_with_real_db.get_user(user_id)

        assert result is not None
        assert result["id"] == user_id
        assert result["username"] == "testuser"

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
        result = await user_service_with_real_db.register_user(
            user_id=111222333,
            username=None,
            first_name="NoUsername",
        )

        assert result["username"] is None
        assert result["first_name"] == "NoUsername"

    async def test_handles_user_without_last_name(
        self,
        user_service_with_real_db: UserService,
    ) -> None:
        """Test handling users without last name."""
        result = await user_service_with_real_db.register_user(
            user_id=444555666,
            username=None,
            first_name="OnlyFirstName",
            last_name=None,
        )

        assert result["last_name"] is None
        assert result["first_name"] == "OnlyFirstName"

    async def test_preserves_user_id_from_telegram(
        self,
        user_service_with_real_db: UserService,
    ) -> None:
        """Test that Telegram user_id is preserved exactly."""
        telegram_id = 123456789

        result = await user_service_with_real_db.register_user(
            user_id=telegram_id,
            username=None,
            first_name="Test",
        )

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
        result1 = await user_service_with_real_db.register_user(
            user_id=111, username=None, first_name="User1"
        )
        result2 = await user_service_with_real_db.register_user(
            user_id=222, username=None, first_name="User2"
        )
        result3 = await user_service_with_real_db.register_user(
            user_id=333, username=None, first_name="User3"
        )

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
        user_id = 123456

        # Register with English
        await user_service_with_real_db.register_user(
            user_id=user_id,
            username=None,
            first_name="Test",
            language_code="en",
        )

        # Update to Russian
        result = await user_service_with_real_db.register_user(
            user_id=user_id,
            username=None,
            first_name="Test",
            language_code="ru",
        )

        assert result["language_code"] == "ru"

    async def test_register_creates_timestamps(
        self,
        user_service_with_real_db: UserService,
    ) -> None:
        """Test that registration creates timestamps."""
        result = await user_service_with_real_db.register_user(
            user_id=123456789,
            username="testuser",
            first_name="Test",
            last_name="User",
            language_code="en",
        )

        assert "created_at" in result
        assert "updated_at" in result
        assert result["created_at"] is not None
        assert result["updated_at"] is not None
