"""Middleware for automatic group registration."""

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from core.services.group_service import GroupService
from core.services.user_service import UserService

logger = logging.getLogger(__name__)

# Skip DB writes if entity was seen within this window
_CACHE_TTL_SECONDS = 300


class GroupTrackerMiddleware(BaseMiddleware):
    """
    Middleware that automatically registers groups and users.

    Ensures that every group and user interacting with the bot
    is registered in the database. Uses in-memory cache to avoid
    hitting the database on every message.
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
        self._seen_users: dict[int, float] = {}
        self._seen_groups: dict[int, float] = {}

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
            now = time.monotonic()

            if event.from_user and not self._is_cached(
                self._seen_users, event.from_user.id, now
            ):
                try:
                    await self.user_service.register_user(
                        user_id=event.from_user.id,
                        username=event.from_user.username,
                        first_name=event.from_user.first_name,
                        last_name=event.from_user.last_name,
                        language_code=event.from_user.language_code,
                    )
                    self._seen_users[event.from_user.id] = now
                except Exception as e:
                    logger.error(f"Failed to register user: {e}")

            if (
                event.chat
                and event.chat.type in ["group", "supergroup"]
                and not self._is_cached(self._seen_groups, event.chat.id, now)
            ):
                try:
                    await self.group_service.register_group(
                        chat_id=event.chat.id,
                        title=event.chat.title or "Unknown",
                        username=event.chat.username,
                        chat_type=event.chat.type,
                    )
                    self._seen_groups[event.chat.id] = now
                except Exception as e:
                    logger.error(f"Failed to register group: {e}")

        return await handler(event, data)

    @staticmethod
    def _is_cached(cache: dict[int, float], entity_id: int, now: float) -> bool:
        last_seen = cache.get(entity_id)
        return last_seen is not None and (now - last_seen) < _CACHE_TTL_SECONDS
