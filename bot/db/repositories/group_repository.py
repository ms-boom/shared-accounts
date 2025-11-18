"""Repository for Group model database operations.

Pattern from statements/ - repository accepts session, doesn't manage transactions.
"""

import logging
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.exceptions import DatabaseError, GroupNotFoundError
from bot.db.models import Group

logger = logging.getLogger(__name__)


def _row_to_dict(group: Group) -> dict:
    """Convert Group model to dict for backward compatibility."""
    return {
        "id": group.id,
        "title": group.title,
        "username": group.username,
        "type": group.type,
        "created_at": group.created_at,
        "updated_at": group.updated_at,
    }


class GroupRepository:
    """Repository pattern for Group model operations.

    Pattern from statements/ - accepts session, uses flush() not commit().
    Transaction management is handled by caller (use case or test).
    """

    def __init__(self, session: AsyncSession):
        """Initialize repository with session injection.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def get_by_id(self, chat_id: int) -> dict | None:
        """Get group by Telegram chat_id.

        Args:
            chat_id: Telegram chat_id (consistent with Telegram API naming)

        Returns:
            Group data as dict or None if not found

        Raises:
            DatabaseError: If database query fails
        """
        try:
            stmt = sa.select(Group).where(Group.id == chat_id)
            result = await self.session.execute(stmt)
            group = result.scalar_one_or_none()
            return _row_to_dict(group) if group else None
        except Exception as e:
            logger.error(f"Failed to get group {chat_id}: {e}")
            raise DatabaseError(f"Failed to get group: {e}") from e

    async def create(
        self,
        chat_id: int,
        title: str,
        username: str | None,
        chat_type: str,
    ) -> dict:
        """Create a new group record.

        Args:
            chat_id: Telegram chat_id (consistent with Telegram API naming)
            title: Group title
            username: Group username (optional)
            chat_type: Chat type ('group' or 'supergroup')

        Returns:
            Created group data as dict

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            group = Group(
                id=chat_id,
                title=title,
                username=username,
                type=chat_type,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            self.session.add(group)
            await self.session.flush()  # Not commit - transaction managed by caller
            logger.info(f"Created group: {chat_id} ({title})")
            return _row_to_dict(group)
        except Exception as e:
            logger.error(f"Failed to create group {chat_id}: {e}")
            raise DatabaseError(f"Failed to create group: {e}") from e

    async def update(
        self,
        chat_id: int,
        title: str | None = None,
        username: str | None = None,
    ) -> dict:
        """Update group information.

        Args:
            chat_id: Telegram chat_id (consistent with Telegram API naming)
            title: New title (optional)
            username: New username (optional)

        Returns:
            Updated group data as dict

        Raises:
            GroupNotFoundError: If group doesn't exist
            DatabaseError: If database operation fails
        """
        try:
            # Get existing group
            stmt = sa.select(Group).where(Group.id == chat_id)
            result = await self.session.execute(stmt)
            group = result.scalar_one_or_none()

            if not group:
                raise GroupNotFoundError(f"Group {chat_id} not found")

            # Update fields if provided
            if title is not None:
                group.title = title
            if username is not None:
                group.username = username

            group.updated_at = datetime.utcnow()

            await self.session.flush()
            logger.info(f"Updated group: {chat_id}")
            return _row_to_dict(group)
        except GroupNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to update group {chat_id}: {e}")
            raise DatabaseError(f"Failed to update group: {e}") from e

    async def get_all(self) -> list[dict]:
        """Get all groups.

        Returns:
            List of all groups as dicts

        Raises:
            DatabaseError: If database query fails
        """
        try:
            stmt = sa.select(Group).order_by(Group.created_at.desc())
            result = await self.session.execute(stmt)
            groups = result.scalars().all()
            return [_row_to_dict(group) for group in groups]
        except Exception as e:
            logger.error(f"Failed to get all groups: {e}")
            raise DatabaseError(f"Failed to get all groups: {e}") from e
