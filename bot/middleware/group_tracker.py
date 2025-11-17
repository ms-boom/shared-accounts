"""Middleware for automatic group registration."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from bot.services.group_service import GroupService
from bot.services.user_service import UserService

logger = logging.getLogger(__name__)


class GroupTrackerMiddleware(BaseMiddleware):
    """
    Middleware that automatically registers groups and users.

    Ensures that every group and user interacting with the bot
    is registered in the database.
    """

    def __init__(self, group_service: GroupService, user_service: UserService):
        """
        Initialize middleware.

        Args:
            group_service: Service for group operations
            user_service: Service for user operations
        """
        self.group_service = group_service
        self.user_service = user_service

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """
        Process update and track groups/users.

        Args:
            handler: Next handler in chain
            event: Telegram event
            data: Handler data

        Returns:
            Handler result
        """
        if isinstance(event, Message):
            # Register user if present
            if event.from_user:
                try:
                    await self.user_service.register_user(event.from_user)
                except Exception as e:
                    logger.error(f"Failed to register user: {e}")

            # Register group if message is from group
            if event.chat and event.chat.type in ["group", "supergroup"]:
                try:
                    await self.group_service.register_group(event.chat)
                except Exception as e:
                    logger.error(f"Failed to register group: {e}")

        return await handler(event, data)
