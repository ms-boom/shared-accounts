"""Service for managing Telegram users."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from core.db.database import Database
from core.db.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


class UserService:
    """Service for user-related operations."""

    def __init__(self, database: Database):
        """
        Initialize service.

        Args:
            database: Database instance
        """
        self.db = database

    async def register_user(
        self,
        user_id: int,
        username: str | None,
        first_name: str,
        last_name: str | None = None,
        language_code: str | None = None,
    ) -> dict:
        """
        Register a new user or update existing one.

        Routes through SQLiteWriterQueue to avoid pool contention
        with other writers sharing pool_size=1.

        Args:
            user_id: Telegram user_id
            username: User username (optional)
            first_name: User first name
            last_name: User last name (optional)
            language_code: User language code (optional)

        Returns:
            User data as dict
        """

        async def _do_register(session: AsyncSession) -> dict:
            repository = UserRepository(session)
            existing = await repository.get_by_id(user_id)

            if existing:
                logger.info(f"Updating existing user: {user_id}")
                return await repository.update(
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    language_code=language_code,
                )
            else:
                logger.info(f"Registering new user: {user_id}")
                return await repository.create(
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    language_code=language_code,
                )

        return await self.db.writer_queue.execute(_do_register)

    async def get_user(self, user_id: int) -> dict | None:
        """
        Get user by ID.

        Args:
            user_id: Telegram user_id

        Returns:
            User data as dict or None if not found
        """
        async with self.db.session_maker() as session:
            repository = UserRepository(session)
            return await repository.get_by_id(user_id)
