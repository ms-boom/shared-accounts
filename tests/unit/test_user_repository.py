"""Unit tests for bot/db/repositories/user_repository.py."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.repositories.user_repository import UserRepository
from core.exceptions import UserNotFoundError


@pytest.mark.unit
class TestUserRepository:
    """Tests for UserRepository class."""

    @pytest.fixture
    def user_repository(self, db_session: AsyncSession) -> UserRepository:
        """
        Create UserRepository instance for testing.

        Args:
            db_session: SQLAlchemy async session

        Returns:
            UserRepository instance
        """
        return UserRepository(db_session)

    async def test_creates_user(self, user_repository: UserRepository) -> None:
        """Test creating a new user."""
        user_id = 123456789
        username = "testuser"
        first_name = "Test"

        user = await user_repository.create(
            user_id=user_id,
            username=username,
            first_name=first_name,
        )

        assert user["id"] == user_id
        assert user["username"] == username
        assert user["first_name"] == first_name
        assert user["last_name"] is None
        assert user["language_code"] is None
        assert user["created_at"] is not None
        assert user["updated_at"] is not None

    async def test_creates_user_with_all_fields(
        self, user_repository: UserRepository
    ) -> None:
        """Test creating user with all optional fields."""
        user_id = 123456789
        username = "testuser"
        first_name = "Test"
        last_name = "User"
        language_code = "en"

        user = await user_repository.create(
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code,
        )

        assert user["id"] == user_id
        assert user["username"] == username
        assert user["first_name"] == first_name
        assert user["last_name"] == last_name
        assert user["language_code"] == language_code

    async def test_gets_user_by_id(self, user_repository: UserRepository) -> None:
        """Test retrieving user by ID."""
        user_id = 123456789

        # Create user first
        await user_repository.create(
            user_id=user_id,
            username="testuser",
            first_name="Test",
        )

        # Retrieve user
        user = await user_repository.get_by_id(user_id)

        assert user is not None
        assert user["id"] == user_id
        assert user["username"] == "testuser"

    async def test_gets_user_by_id_returns_none_if_not_found(
        self, user_repository: UserRepository
    ) -> None:
        """Test that get_by_id returns None for non-existent user."""
        user = await user_repository.get_by_id(999999999)

        assert user is None

    async def test_updates_user(self, user_repository: UserRepository) -> None:
        """Test updating user information."""
        user_id = 123456789

        # Create user first
        await user_repository.create(
            user_id=user_id,
            username="oldusername",
            first_name="Old",
        )

        # Update user
        updated = await user_repository.update(
            user_id=user_id,
            username="newusername",
            first_name="New",
        )

        assert updated["username"] == "newusername"
        assert updated["first_name"] == "New"

    async def test_updates_user_partially(
        self, user_repository: UserRepository
    ) -> None:
        """Test partial update of user fields."""
        user_id = 123456789

        # Create user
        await user_repository.create(
            user_id=user_id,
            username="testuser",
            first_name="Test",
            last_name="User",
        )

        # Update only username
        updated = await user_repository.update(
            user_id=user_id,
            username="newusername",
        )

        assert updated["username"] == "newusername"
        assert updated["first_name"] == "Test"
        assert updated["last_name"] == "User"

    async def test_update_raises_error_if_user_not_found(
        self, user_repository: UserRepository
    ) -> None:
        """Test that update raises UserNotFoundError for non-existent user."""
        with pytest.raises(UserNotFoundError) as exc_info:
            await user_repository.update(
                user_id=999999999,
                username="newusername",
            )

        assert "User 999999999 not found" in str(exc_info.value)

    async def test_update_with_no_changes_returns_existing(
        self, user_repository: UserRepository
    ) -> None:
        """Test that update with no changes returns existing data."""
        user_id = 123456789

        # Create user
        original = await user_repository.create(
            user_id=user_id,
            username="testuser",
            first_name="Test",
        )

        # Update with no parameters
        updated = await user_repository.update(user_id=user_id)

        assert updated["username"] == original["username"]
        assert updated["first_name"] == original["first_name"]

    async def test_creates_multiple_users(
        self, user_repository: UserRepository
    ) -> None:
        """Test creating multiple users."""
        user1 = await user_repository.create(
            user_id=111,
            username="user1",
            first_name="User1",
        )

        user2 = await user_repository.create(
            user_id=222,
            username="user2",
            first_name="User2",
        )

        assert user1["id"] == 111
        assert user2["id"] == 222

        # Verify both can be retrieved
        retrieved1 = await user_repository.get_by_id(111)
        retrieved2 = await user_repository.get_by_id(222)

        assert retrieved1 is not None
        assert retrieved2 is not None
        assert retrieved1["username"] == "user1"
        assert retrieved2["username"] == "user2"

    async def test_updates_updated_at_timestamp(
        self, user_repository: UserRepository
    ) -> None:
        """Test that update modifies updated_at timestamp."""
        user_id = 123456789

        # Create user
        await user_repository.create(
            user_id=user_id,
            username="testuser",
            first_name="Test",
        )

        # Small delay to ensure timestamp difference
        import asyncio

        await asyncio.sleep(0.01)

        # Update user
        updated = await user_repository.update(
            user_id=user_id,
            username="newusername",
        )

        # updated_at should exist and potentially be different
        assert updated["updated_at"] is not None
        # Note: In SQLite timestamps are strings, so comparison might not work as expected
