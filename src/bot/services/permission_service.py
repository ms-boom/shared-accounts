"""Service for checking user permissions in groups."""

import logging
from datetime import datetime

from aiogram import Bot

from core.config import Settings

logger = logging.getLogger(__name__)


class PermissionService:
    """
    Service for checking user permissions with caching.

    Caches permission checks to reduce Telegram API calls.
    """

    def __init__(self, settings: Settings):
        """
        Initialize service.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.cache_ttl = settings.PERMISSION_CACHE_TTL
        self._cache: dict[str, tuple[bool, datetime]] = {}

    def _get_cache_key(self, user_id: int, chat_id: int) -> str:
        """Generate cache key for permission check."""
        return f"{user_id}:{chat_id}"

    def _is_cache_valid(self, cached_at: datetime) -> bool:
        """Check if cached value is still valid."""
        return (datetime.utcnow() - cached_at).total_seconds() < self.cache_ttl

    async def is_group_admin(self, bot: Bot, user_id: int, chat_id: int) -> bool:
        """
        Check if user is administrator in a group.

        Uses caching to reduce API calls.

        Args:
            bot: Bot instance
            user_id: Telegram user_id
            chat_id: Telegram chat_id

        Returns:
            True if user is admin or creator, False otherwise
        """
        cache_key = self._get_cache_key(user_id, chat_id)

        # Check cache
        if cache_key in self._cache:
            is_admin, cached_at = self._cache[cache_key]
            if self._is_cache_valid(cached_at):
                logger.debug(
                    f"Permission cache hit for user {user_id} in chat {chat_id}"
                )
                return is_admin

        # Query Telegram API
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            is_admin = member.status in ["administrator", "creator"]

            # Cache result
            self._cache[cache_key] = (is_admin, datetime.utcnow())
            logger.debug(
                f"Checked permissions for user {user_id} in chat {chat_id}: {is_admin}"
            )

            return is_admin
        except Exception as e:
            logger.error(f"Failed to check permissions for user {user_id}: {e}")
            # Invalidate cache on error
            if cache_key in self._cache:
                del self._cache[cache_key]
            return False

    def invalidate_cache(
        self, user_id: int | None = None, chat_id: int | None = None
    ) -> None:
        """
        Invalidate permission cache.

        Args:
            user_id: User ID to invalidate (all if None)
            chat_id: Chat ID to invalidate (all if None)
        """
        if user_id is None and chat_id is None:
            # Clear entire cache
            self._cache.clear()
            logger.info("Cleared entire permission cache")
        else:
            # Clear specific entries
            keys_to_delete = []
            for key in self._cache:
                u_id, c_id = map(int, key.split(":"))
                if (user_id is None or u_id == user_id) and (
                    chat_id is None or c_id == chat_id
                ):
                    keys_to_delete.append(key)

            for key in keys_to_delete:
                del self._cache[key]

            logger.info(f"Invalidated {len(keys_to_delete)} permission cache entries")
