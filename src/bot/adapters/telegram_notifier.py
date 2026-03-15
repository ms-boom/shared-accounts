"""TelegramNotifier — implements TaskNotifier using aiogram Bot."""

import logging

from aiogram import Bot

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Sends task results to Telegram chat or topic via aiogram Bot.

    Implements core.ports.TaskNotifier protocol.
    Created in bot/container.py and injected into TaskWorker.
    """

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def notify_success(self, chat_id: int, thread_id: int, message: str) -> None:
        await self._send(chat_id, thread_id, message)

    async def notify_error(self, chat_id: int, thread_id: int, error: str) -> None:
        await self._send(chat_id, thread_id, f"❌ {error}")

    async def _send(
        self,
        chat_id: int,
        thread_id: int,
        text: str,
        parse_mode: str | None = None,
    ) -> None:
        try:
            kwargs: dict = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
            if thread_id:
                kwargs["message_thread_id"] = thread_id
            await self.bot.send_message(**kwargs)
        except Exception as e:
            logger.error("Failed to send message to %d/%d: %s", chat_id, thread_id, e)
