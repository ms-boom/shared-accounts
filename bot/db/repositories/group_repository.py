"""Repository for Group model database operations."""

import logging
from datetime import datetime

from databases import Database

from bot.core.exceptions import DatabaseError, GroupNotFoundError
from bot.db.models import Group

logger = logging.getLogger(__name__)


class GroupRepository:
    """Repository pattern for Group model operations."""

    def __init__(self, database: Database):
        """
        Initialize repository.

        Args:
            database: Database connection instance
        """
        self.db = database

    async def get_by_id(self, group_id: int) -> dict | None:
        """
        Get group by Telegram chat_id.

        Args:
            group_id: Telegram chat_id

        Returns:
            Group data as dict or None if not found

        Raises:
            DatabaseError: If database query fails
        """
        query = """
            SELECT id, title, username, type, created_at, updated_at
            FROM groups
            WHERE id = :group_id
        """
        try:
            result = await self.db.fetch_one(query, {"group_id": group_id})
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Failed to get group {group_id}: {e}")
            raise DatabaseError(f"Failed to get group: {e}") from e

    async def create(
        self,
        group_id: int,
        title: str,
        username: str | None,
        chat_type: str,
    ) -> dict:
        """
        Create a new group record.

        Args:
            group_id: Telegram chat_id
            title: Group title
            username: Group username (optional)
            chat_type: Chat type ('group' or 'supergroup')

        Returns:
            Created group data as dict

        Raises:
            DatabaseError: If database operation fails
        """
        query = """
            INSERT INTO groups (id, title, username, type, created_at, updated_at)
            VALUES (:id, :title, :username, :type, :created_at, :updated_at)
            RETURNING id, title, username, type, created_at, updated_at
        """
        now = datetime.utcnow()
        values = {
            "id": group_id,
            "title": title,
            "username": username,
            "type": chat_type,
            "created_at": now,
            "updated_at": now,
        }

        try:
            result = await self.db.fetch_one(query, values)
            logger.info(f"Created group: {group_id} ({title})")
            return dict(result) if result else values
        except Exception as e:
            logger.error(f"Failed to create group {group_id}: {e}")
            raise DatabaseError(f"Failed to create group: {e}") from e

    async def update(
        self,
        group_id: int,
        title: str | None = None,
        username: str | None = None,
    ) -> dict:
        """
        Update group information.

        Args:
            group_id: Telegram chat_id
            title: New title (optional)
            username: New username (optional)

        Returns:
            Updated group data as dict

        Raises:
            GroupNotFoundError: If group doesn't exist
            DatabaseError: If database operation fails
        """
        # Check if group exists
        existing = await self.get_by_id(group_id)
        if not existing:
            raise GroupNotFoundError(f"Group {group_id} not found")

        # Build update query dynamically
        updates = []
        values = {"group_id": group_id, "updated_at": datetime.utcnow()}

        if title is not None:
            updates.append("title = :title")
            values["title"] = title

        if username is not None:
            updates.append("username = :username")
            values["username"] = username

        if not updates:
            return existing

        updates.append("updated_at = :updated_at")
        query = f"""
            UPDATE groups
            SET {', '.join(updates)}
            WHERE id = :group_id
            RETURNING id, title, username, type, created_at, updated_at
        """

        try:
            result = await self.db.fetch_one(query, values)
            logger.info(f"Updated group: {group_id}")
            return dict(result) if result else existing
        except Exception as e:
            logger.error(f"Failed to update group {group_id}: {e}")
            raise DatabaseError(f"Failed to update group: {e}") from e

    async def get_all(self) -> list[dict]:
        """
        Get all groups.

        Returns:
            List of all groups as dicts

        Raises:
            DatabaseError: If database query fails
        """
        query = """
            SELECT id, title, username, type, created_at, updated_at
            FROM groups
            ORDER BY created_at DESC
        """
        try:
            results = await self.db.fetch_all(query)
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Failed to get all groups: {e}")
            raise DatabaseError(f"Failed to get all groups: {e}") from e
