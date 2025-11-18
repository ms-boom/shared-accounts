"""Worker service entry point."""

import asyncio
import logging
import signal
import sys

from aiogram import Bot

from bot.core.config import get_settings
from bot.db.database import Database
from bot.worker.task_worker import TaskWorker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


async def main() -> None:
    """Run the task worker."""
    settings = get_settings()

    # Create data directories
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.SESSION_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
    settings.ERROR_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize database connection
    database = Database(settings)
    await database.startup()
    logger.info(f"Connected to database: {settings.DATABASE_URL}")

    # Initialize Telegram bot
    bot = Bot(token=settings.TELEGRAM_TOKEN)

    # Create and start worker
    worker = TaskWorker(database, bot, settings)

    # Handle graceful shutdown
    stop_event = asyncio.Event()

    def signal_handler(sig: int) -> None:
        logger.info(f"Received signal {sig}, shutting down...")
        stop_event.set()

    def make_signal_handler(sig: int):
        return lambda: signal_handler(sig)

    # Register signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, make_signal_handler(sig))

    try:
        # Run worker until signal received
        worker_task = asyncio.create_task(worker.run())
        await stop_event.wait()

        # Stop worker
        await worker.stop()
        worker_task.cancel()

        try:
            await worker_task
        except asyncio.CancelledError:
            pass

    finally:
        # Cleanup
        await database.shutdown()
        await bot.session.close()
        logger.info("Worker shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
        sys.exit(0)
