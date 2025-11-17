"""Service for managing Telegram users."""

import logging

from aiogram.types import User as TelegramUser

from bot.db.database import Database
from bot.db.repositories.user_repository import UserRepository

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
        self.repository = UserRepository(database.get_connection())

    async def register_user(self, user: TelegramUser) -> dict:
        """
        Register a new user or update existing one.

        Args:
            user: Telegram User object

        Returns:
            User data as dict
        """
        user_id = user.id
        existing = await self.repository.get_by_id(user_id)

        if existing:
            # Update existing user info
            logger.info(f"Updating existing user: {user_id}")
            return await self.repository.update(
                user_id=user_id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                language_code=user.language_code,
            )
        else:
            # Create new user
            logger.info(f"Registering new user: {user_id}")
            return await self.repository.create(
                user_id=user_id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                language_code=user.language_code,
            )

    async def get_user(self, user_id: int) -> dict | None:
        """
        Get user by ID.

        Args:
            user_id: Telegram user_id

        Returns:
            User data as dict or None if not found
        """
        return await self.repository.get_by_id(user_id)
