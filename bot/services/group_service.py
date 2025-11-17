"""Service for managing Telegram groups."""

import logging

from aiogram.types import Chat

from bot.db.database import Database
from bot.db.repositories.group_repository import GroupRepository

logger = logging.getLogger(__name__)


class GroupService:
    """Service for group-related operations."""

    def __init__(self, database: Database):
        """
        Initialize service.

        Args:
            database: Database instance
        """
        self.db = database
        self.repository = GroupRepository(database.get_connection())

    async def register_group(self, chat: Chat) -> dict:
        """
        Register a new group or update existing one.

        Args:
            chat: Telegram Chat object

        Returns:
            Group data as dict
        """
        group_id = chat.id
        existing = await self.repository.get_by_id(group_id)

        if existing:
            # Update existing group info
            logger.info(f"Updating existing group: {group_id}")
            return await self.repository.update(
                group_id=group_id,
                title=chat.title,
                username=chat.username,
            )
        else:
            # Create new group
            logger.info(f"Registering new group: {group_id}")
            return await self.repository.create(
                group_id=group_id,
                title=chat.title or "Unknown",
                username=chat.username,
                chat_type=chat.type,
            )

    async def get_group(self, group_id: int) -> dict | None:
        """
        Get group by ID.

        Args:
            group_id: Telegram chat_id

        Returns:
            Group data as dict or None if not found
        """
        return await self.repository.get_by_id(group_id)

    async def get_all_groups(self) -> list[dict]:
        """
        Get all registered groups.

        Returns:
            List of all groups
        """
        return await self.repository.get_all()

    async def update_group_info(
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
            Updated group data
        """
        return await self.repository.update(
            group_id=group_id,
            title=title,
            username=username,
        )
