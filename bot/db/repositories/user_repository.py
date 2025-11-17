"""Repository for User model database operations."""

import logging
from datetime import datetime

from databases import Database

from bot.core.exceptions import DatabaseError, UserNotFoundError

logger = logging.getLogger(__name__)


class UserRepository:
    """Repository pattern for User model operations."""

    def __init__(self, database: Database):
        """
        Initialize repository.

        Args:
            database: Database connection instance
        """
        self.db = database

    async def get_by_id(self, user_id: int) -> dict | None:
        """
        Get user by Telegram user_id.

        Args:
            user_id: Telegram user_id

        Returns:
            User data as dict or None if not found

        Raises:
            DatabaseError: If database query fails
        """
        query = """
            SELECT id, username, first_name, last_name, language_code, created_at, updated_at
            FROM users
            WHERE id = :user_id
        """
        try:
            result = await self.db.fetch_one(query, {"user_id": user_id})
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Failed to get user {user_id}: {e}")
            raise DatabaseError(f"Failed to get user: {e}") from e

    async def create(
        self,
        user_id: int,
        username: str | None,
        first_name: str,
        last_name: str | None = None,
        language_code: str | None = None,
    ) -> dict:
        """
        Create a new user record.

        Args:
            user_id: Telegram user_id
            username: User username (optional)
            first_name: User first name
            last_name: User last name (optional)
            language_code: User language code (optional)

        Returns:
            Created user data as dict

        Raises:
            DatabaseError: If database operation fails
        """
        query = """
            INSERT INTO users (id, username, first_name, last_name, language_code, created_at, updated_at)
            VALUES (:id, :username, :first_name, :last_name, :language_code, :created_at, :updated_at)
            RETURNING id, username, first_name, last_name, language_code, created_at, updated_at
        """
        now = datetime.utcnow()
        values = {
            "id": user_id,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "language_code": language_code,
            "created_at": now,
            "updated_at": now,
        }

        try:
            result = await self.db.fetch_one(query, values)
            logger.info(f"Created user: {user_id} ({first_name})")
            return dict(result) if result else values
        except Exception as e:
            logger.error(f"Failed to create user {user_id}: {e}")
            raise DatabaseError(f"Failed to create user: {e}") from e

    async def update(
        self,
        user_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        language_code: str | None = None,
    ) -> dict:
        """
        Update user information.

        Args:
            user_id: Telegram user_id
            username: New username (optional)
            first_name: New first name (optional)
            last_name: New last name (optional)
            language_code: New language code (optional)

        Returns:
            Updated user data as dict

        Raises:
            UserNotFoundError: If user doesn't exist
            DatabaseError: If database operation fails
        """
        # Check if user exists
        existing = await self.get_by_id(user_id)
        if not existing:
            raise UserNotFoundError(f"User {user_id} not found")

        # Build update query dynamically
        updates = []
        values = {"user_id": user_id, "updated_at": datetime.utcnow()}

        if username is not None:
            updates.append("username = :username")
            values["username"] = username

        if first_name is not None:
            updates.append("first_name = :first_name")
            values["first_name"] = first_name

        if last_name is not None:
            updates.append("last_name = :last_name")
            values["last_name"] = last_name

        if language_code is not None:
            updates.append("language_code = :language_code")
            values["language_code"] = language_code

        if not updates:
            return existing

        updates.append("updated_at = :updated_at")
        query = f"""
            UPDATE users
            SET {', '.join(updates)}
            WHERE id = :user_id
            RETURNING id, username, first_name, last_name, language_code, created_at, updated_at
        """

        try:
            result = await self.db.fetch_one(query, values)
            logger.info(f"Updated user: {user_id}")
            return dict(result) if result else existing
        except Exception as e:
            logger.error(f"Failed to update user {user_id}: {e}")
            raise DatabaseError(f"Failed to update user: {e}") from e
