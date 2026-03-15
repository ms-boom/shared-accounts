"""Core interfaces (Protocols) for cross-layer communication.

Core defines contracts. External layers (bot, api, etc.) provide implementations.
"""

import logging
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class TaskNotifier(Protocol):
    """Interface for notifying users about task results.

    Core defines this contract. Bot layer provides TelegramNotifier.
    Worker uses LoggingNotifier when running standalone.
    """

    async def notify_success(
        self, chat_id: int, thread_id: int, message: str
    ) -> None: ...

    async def notify_error(self, chat_id: int, thread_id: int, error: str) -> None: ...


class LoggingNotifier:
    """Default notifier that logs results to the application log.

    Used when TaskWorker runs standalone (python -m core.worker)
    without a Telegram bot connected.
    """

    async def notify_success(self, chat_id: int, thread_id: int, message: str) -> None:
        logger.info("Task success [%d/%d]: %s", chat_id, thread_id, message)

    async def notify_error(self, chat_id: int, thread_id: int, error: str) -> None:
        logger.warning("Task error [%d/%d]: %s", chat_id, thread_id, error)
