"""Service for managing Telegram groups."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from core.db.database import Database
from core.db.repositories.group_repository import GroupRepository

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

    async def register_group(
        self,
        chat_id: int,
        title: str,
        username: str | None,
        chat_type: str,
    ) -> dict:
        """
        Register a new group or update existing one.

        Routes through SQLiteWriterQueue to avoid pool contention
        with other writers sharing pool_size=1.

        Args:
            chat_id: Telegram chat_id
            title: Group title
            username: Group username (optional)
            chat_type: Chat type ('group' or 'supergroup')

        Returns:
            Group data as dict
        """

        async def _do_register(session: AsyncSession) -> dict:
            repository = GroupRepository(session)
            existing = await repository.get_by_id(chat_id)

            if existing:
                logger.info(f"Updating existing group: {chat_id}")
                return await repository.update(
                    chat_id=chat_id,
                    title=title,
                    username=username,
                )
            else:
                logger.info(f"Registering new group: {chat_id}")
                return await repository.create(
                    chat_id=chat_id,
                    title=title,
                    username=username,
                    chat_type=chat_type,
                )

        return await self.db.write(_do_register)

    async def get_group(self, group_id: int) -> dict | None:
        """
        Get group by ID.

        Args:
            group_id: Telegram chat_id

        Returns:
            Group data as dict or None if not found
        """
        async with self.db.read() as session:
            repository = GroupRepository(session)
            return await repository.get_by_id(group_id)

    async def get_all_groups(self) -> list[dict]:
        """
        Get all registered groups.

        Returns:
            List of all groups
        """
        async with self.db.read() as session:
            repository = GroupRepository(session)
            return await repository.get_all()

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

        async def _do_update(session: AsyncSession) -> dict:
            repository = GroupRepository(session)
            return await repository.update(
                chat_id=group_id,
                title=title,
                username=username,
            )

        return await self.db.write(_do_update)
