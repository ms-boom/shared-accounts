"""Global error handling middleware."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from bot.core.exceptions import BotError

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseMiddleware):
    """
    Middleware for global error handling.

    Catches exceptions in handlers and provides user-friendly error messages.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """
        Process update and handle errors.

        Args:
            handler: Next handler in chain
            event: Telegram event
            data: Handler data

        Returns:
            Handler result or None if error occurred
        """
        try:
            return await handler(event, data)
        except BotError as e:
            # Known bot errors - log and inform user
            logger.warning("Bot error: %s", e)
            await self._send_error_message(event, str(e))
        except Exception as e:
            # Unknown errors - log with stack trace
            logger.exception("Unexpected error: %s", e)
            await self._send_error_message(event, "Произошла ошибка. Попробуйте позже.")
        return None

    async def _send_error_message(self, event: TelegramObject, message: str) -> None:
        """
        Send error message to user.

        Args:
            event: Telegram event
            message: Error message to send
        """
        try:
            if isinstance(event, Update) and event.message:
                await event.message.reply(f"❌ {message}")
            elif isinstance(event, Update) and event.callback_query:
                await event.callback_query.answer(message, show_alert=True)
        except Exception as e:
            logger.error("Failed to send error message: %s", e)
