"""Task worker for processing background tasks from queue."""

import asyncio
import logging

from aiogram import Bot
from databases import Database

from bot.core.config import Settings
from bot.core.exceptions import BrowserError, SessionError, TaskError
from bot.db.repositories.chat_session_repository import ChatSessionRepository
from bot.db.repositories.task_repository import TaskRepository
from bot.worker.playwright_service import PlaywrightService

logger = logging.getLogger(__name__)


class TaskWorker:
    """
    Background worker for processing tasks from the queue.

    Polls tasks table, processes tasks with Playwright, sends results via Telegram.
    """

    def __init__(
        self,
        database: Database,
        bot: Bot,
        settings: Settings,
    ):
        """
        Initialize task worker.

        Args:
            database: Database connection
            bot: Telegram bot instance for sending messages
            settings: Application settings
        """
        self.db = database
        self.bot = bot
        self.settings = settings
        self.playwright = PlaywrightService(settings)
        self.task_repo = TaskRepository(database)
        self.session_repo = ChatSessionRepository(database)
        self.running = False

    async def start(self) -> None:
        """Start the worker and Playwright browser."""
        logger.info("Starting task worker...")
        self.running = True
        await self.playwright.start()
        logger.info("Task worker started")

    async def stop(self) -> None:
        """Stop the worker and Playwright browser."""
        logger.info("Stopping task worker...")
        self.running = False
        await self.playwright.stop()
        logger.info("Task worker stopped")

    async def run(self) -> None:
        """
        Main worker loop: poll for tasks and process them.

        Runs until stop() is called.
        """
        await self.start()

        try:
            while self.running:
                try:
                    # Dequeue next pending task
                    task = await self.task_repo.dequeue_pending_task()

                    if task:
                        await self.process_task(task)
                    else:
                        # No tasks, wait before polling again
                        await asyncio.sleep(self.settings.WORKER_POLL_INTERVAL)

                except Exception as e:
                    logger.error(f"Error in worker loop: {e}", exc_info=True)
                    await asyncio.sleep(self.settings.WORKER_POLL_INTERVAL)

        finally:
            await self.stop()

    async def process_task(self, task: dict) -> None:
        """
        Process a single task.

        Args:
            task: Task data from database
        """
        task_id = task["id"]
        task_type = task["task_type"]
        chat_id = task["chat_id"]
        payload = task["payload"]

        logger.info(f"Processing task {task_id}: {task_type}")

        try:
            if task_type == "init_session":
                await self.process_init_session(task_id, chat_id, payload)
            elif task_type == "process_login_link":
                await self.process_login_link(task_id, chat_id, payload)
            elif task_type == "get_code":
                await self.process_get_code(task_id, chat_id, payload)
            else:
                raise TaskError(f"Unknown task type: {task_type}")

        except (BrowserError, SessionError, TaskError) as e:
            logger.error(f"Task {task_id} failed: {e}")
            await self.task_repo.update_status(task_id, "failed", str(e))
            await self.send_message(chat_id, str(e))

        except Exception as e:
            logger.error(
                f"Unexpected error processing task {task_id}: {e}", exc_info=True
            )
            await self.task_repo.update_status(
                task_id, "failed", f"Internal error: {str(e)}"
            )
            await self.send_message(
                chat_id,
                "❌ An unexpected error occurred. Please try again later.",
            )

    async def process_init_session(
        self,
        task_id: str,
        chat_id: int,
        payload: dict,
    ) -> None:
        """
        Process init_session task.

        Args:
            task_id: Task UUID
            chat_id: Telegram chat_id
            payload: Task payload with 'email' field
        """
        email = payload.get("email")
        if not email:
            raise TaskError("Missing 'email' in payload")

        # Initialize session with Playwright
        session_path, message = await self.playwright.initialize_session(chat_id, email)

        # Create session record in database
        await self.session_repo.upsert(
            chat_id=chat_id,
            email=email,
            session_path=session_path,
        )

        # Mark task as done
        await self.task_repo.update_status(task_id, "done", message)

        # Send result to user
        await self.send_message(chat_id, message)

    async def process_login_link(
        self,
        task_id: str,
        chat_id: int,
        payload: dict,
    ) -> None:
        """
        Process login link to complete authentication.

        Args:
            task_id: Task UUID
            chat_id: Telegram chat_id
            payload: Task payload with 'login_url' field
        """
        login_url = payload.get("login_url")
        if not login_url:
            raise TaskError("Missing 'login_url' in payload")

        # Process login link
        message = await self.playwright.process_login_link(chat_id, login_url)

        # Mark task as done
        await self.task_repo.update_status(task_id, "done", message)

        # Send result to user
        await self.send_message(chat_id, message)

    async def process_get_code(
        self,
        task_id: str,
        chat_id: int,
        payload: dict,
    ) -> None:
        """
        Process get_code task.

        Args:
            task_id: Task UUID
            chat_id: Telegram chat_id
            payload: Task payload with 'auth_url' field
        """
        auth_url = payload.get("auth_url")
        if not auth_url:
            raise TaskError("Missing 'auth_url' in payload")

        # Extract authorization code
        code = await self.playwright.extract_authorization_code(chat_id, auth_url)

        # Update last_used for session
        await self.session_repo.update_last_used(chat_id)

        # Mark task as done
        await self.task_repo.update_status(task_id, "done", code)

        # Send code to user
        message = f"✅ Authorization code: `{code}`"
        await self.send_message(chat_id, message, parse_mode="Markdown")

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str | None = None,
    ) -> None:
        """
        Send message to Telegram chat.

        Args:
            chat_id: Telegram chat_id
            text: Message text
            parse_mode: Parse mode (None, "Markdown", "HTML")
        """
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
            )
        except Exception as e:
            logger.error(f"Failed to send message to {chat_id}: {e}")
