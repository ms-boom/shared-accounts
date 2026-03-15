"""Main entry point for the Telegram bot."""

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.adapters.telegram_notifier import TelegramNotifier
from bot.container import create_container
from bot.db.fsm_storage import BotFSMStorage
from bot.handlers import claude_auth, common, group_admin, group_events
from bot.middleware.error_handler import ErrorHandlerMiddleware
from bot.middleware.group_tracker import GroupTrackerMiddleware
from bot.services.permission_service import PermissionService
from core.config import get_settings
from core.db.database import Database
from core.logging_config import setup_logging
from core.services.group_service import GroupService
from core.services.user_service import UserService
from core.worker.task_worker import TaskWorker

logger = logging.getLogger(__name__)


async def on_startup(bot: Bot, database: Database, debug: bool = False) -> None:
    """
    Execute on bot startup.

    Args:
        bot: Bot instance
        database: Database instance
        debug: Debug mode flag
    """
    logger.info("Bot starting up...")

    # Initialize database
    await database.startup()

    # Create tables (WARNING: Use migrations in production!)
    if debug:
        logger.warning("Creating database tables (development mode)")
        await database.create_tables()

    logger.info("Bot startup complete")


async def on_shutdown(bot: Bot, database: Database) -> None:
    """
    Execute on bot shutdown.

    Args:
        bot: Bot instance
        database: Database instance
    """
    logger.info("Bot shutting down...")

    # Close database connection
    await database.shutdown()

    # Close bot session
    await bot.session.close()

    logger.info("Bot shutdown complete")


def _on_worker_done(task: asyncio.Task) -> None:
    """Log unexpected worker task exit without crashing the bot."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error("Task worker exited unexpectedly: %s", exc, exc_info=exc)
    else:
        logger.warning("Task worker finished without error (unexpected during polling)")


async def main() -> None:
    """Main function to run the bot."""
    # Load settings
    settings = get_settings()

    # Setup logging
    setup_logging(settings)

    logger.info("Starting Telegram Bot Template")
    logger.info(f"Debug mode: {settings.DEBUG}")

    # Create DI container
    container = create_container(settings)

    # Resolve dependencies
    database = container.resolve(Database)
    permission_service = PermissionService(settings)
    group_service = GroupService(database)
    user_service = UserService(database)

    # Create bot
    bot = Bot(
        token=settings.TELEGRAM_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Startup database (must be done before creating FSM storage)
    await on_startup(bot, database, settings.DEBUG)

    # Use BotFSMStorage for FSM (persistent state across bot restarts)
    storage = BotFSMStorage(database.session_maker, writer_queue=database.writer_queue)
    dp = Dispatcher(storage=storage)

    # Register middleware
    dp.message.middleware(ErrorHandlerMiddleware())
    dp.message.middleware(GroupTrackerMiddleware(group_service, user_service))

    # Make services available to handlers via dependency injection
    dp["permission_service"] = permission_service
    dp["group_service"] = group_service
    dp["user_service"] = user_service
    dp["database"] = database
    dp["settings"] = settings

    # Register routers
    dp.include_router(common.router)
    dp.include_router(claude_auth.router)
    dp.include_router(group_events.router)
    dp.include_router(group_admin.router)

    # Start task worker as inline asyncio task (shares SQLiteWriterQueue with bot)
    worker = TaskWorker(database, settings, TelegramNotifier(bot))
    worker_task = asyncio.create_task(worker.run(), name="task-worker")
    worker_task.add_done_callback(_on_worker_done)

    try:
        # Start polling
        logger.info("Starting polling...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.exception(f"Error during polling: {e}")
    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
        await on_shutdown(bot, database)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
