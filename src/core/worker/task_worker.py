"""Task worker for processing background tasks from queue."""

import asyncio
import logging

from core.config import Settings
from core.db.database import Database
from core.db.repositories.chat_session_repository import ChatSessionRepository
from core.db.repositories.task_repository import TaskRepository
from core.exceptions import BrowserError, SessionError, TaskError
from core.ports import LoggingNotifier, TaskNotifier
from core.worker.playwright_service import PlaywrightService

logger = logging.getLogger(__name__)


class TaskWorker:
    """Background worker for processing tasks from the queue.

    Polls tasks table, processes tasks with Playwright, sends results via notifier.
    Uses SQLAlchemy sessions with proper transaction management.
    """

    def __init__(
        self,
        database: Database,
        settings: Settings,
        notifier: TaskNotifier | None = None,
    ):
        """Initialize task worker.

        Args:
            database: Database manager with session factory
            settings: Application settings
            notifier: Notifier for sending results to users. Defaults to LoggingNotifier.
        """
        self.db = database
        self.settings = settings
        self.notifier: TaskNotifier = notifier or LoggingNotifier()
        self.playwright = PlaywrightService(settings)
        self.running = False
        self.recovery_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the worker and Playwright browser."""
        logger.info("Starting task worker...")
        self.running = True
        await self.playwright.start()

        # Start recovery task for stuck tasks
        self.recovery_task = asyncio.create_task(self._recovery_loop())
        logger.info("Task worker started")

    async def stop(self) -> None:
        """Stop the worker and Playwright browser."""
        logger.info("Stopping task worker...")
        self.running = False

        # Stop recovery task
        if self.recovery_task:
            self.recovery_task.cancel()
            try:
                await self.recovery_task
            except asyncio.CancelledError:
                pass

        await self.playwright.stop()
        logger.info("Task worker stopped")

    async def run(self) -> None:
        """Main worker loop: poll for tasks and process them.

        Runs until stop() is called.
        Uses SQLAlchemy sessions with proper transaction management.
        """
        await self.start()

        try:
            while self.running:
                try:
                    # Dequeue next pending task using transaction
                    async with self.db.session_maker() as session, session.begin():
                        task_repo = TaskRepository(session)
                        task = await task_repo.dequeue_pending_task()

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
        task_id: str = str(task["id"])
        task_type = task["task_type"]
        chat_id = task["chat_id"]
        thread_id = task.get("thread_id", 0)
        payload = task["payload"]
        version = task["version"]

        logger.info(f"Processing task {task_id}: {task_type} (version {version})")

        try:
            if task_type == "init_session":
                await self.process_init_session(
                    task_id, chat_id, thread_id, payload, version
                )
            elif task_type == "process_login_link":
                await self.process_login_link(
                    task_id, chat_id, thread_id, payload, version
                )
            elif task_type == "get_code":
                await self.process_get_code(
                    task_id, chat_id, thread_id, payload, version
                )
            else:
                raise TaskError(f"Unknown task type: {task_type}")

        except (BrowserError, SessionError, TaskError) as e:
            logger.error(f"Task {task_id} failed: {e}")
            async with self.db.session_maker() as session, session.begin():
                task_repo = TaskRepository(session)
                result = await task_repo.update_status(
                    task_id, "failed", version, str(e)
                )
            if result:
                await self.notifier.notify_error(chat_id, thread_id, str(e))
            else:
                logger.warning(
                    f"Failed to update task {task_id} status: version conflict"
                )

        except Exception as e:
            logger.error(
                f"Unexpected error processing task {task_id}: {e}", exc_info=True
            )
            async with self.db.session_maker() as session, session.begin():
                task_repo = TaskRepository(session)
                result = await task_repo.update_status(
                    task_id, "failed", version, f"Internal error: {str(e)}"
                )
            if result:
                await self.notifier.notify_error(
                    chat_id,
                    thread_id,
                    "An unexpected error occurred. Please try again later.",
                )
            else:
                logger.warning(
                    f"Failed to update task {task_id} status: version conflict"
                )

    async def process_init_session(
        self,
        task_id: str,
        chat_id: int,
        thread_id: int,
        payload: dict,
        version: int,
    ) -> None:
        """
        Process init_session task.

        Args:
            task_id: Task ID string
            chat_id: Telegram chat_id
            thread_id: Telegram thread_id
            payload: Task payload with 'email' field
            version: Task version for optimistic locking
        """
        email = payload.get("email")
        if not email:
            raise TaskError("Missing 'email' in payload")

        # Initialize session with Playwright
        session_path, message = await self.playwright.initialize_session(
            chat_id, email, thread_id
        )

        # Create session record and mark task as done in transaction
        async with self.db.session_maker() as session, session.begin():
            session_repo = ChatSessionRepository(session)
            await session_repo.upsert(
                chat_id=chat_id,
                email=email,
                session_path=session_path,
                thread_id=thread_id,
            )

            task_repo = TaskRepository(session)
            result = await task_repo.update_status(task_id, "done", version, message)

        if not result:
            logger.warning(f"Task {task_id} update failed: version conflict")
            return

        # Send result to user
        await self.notifier.notify_success(chat_id, thread_id, message)

    async def process_login_link(
        self,
        task_id: str,
        chat_id: int,
        thread_id: int,
        payload: dict,
        version: int,
    ) -> None:
        """
        Process login link to complete authentication.

        Args:
            task_id: Task ID string
            chat_id: Telegram chat_id
            thread_id: Telegram thread_id
            payload: Task payload with 'login_url' field
            version: Task version for optimistic locking
        """
        login_url = payload.get("login_url")
        if not login_url:
            raise TaskError("Missing 'login_url' in payload")

        # Process login link
        message = await self.playwright.process_login_link(
            chat_id, login_url, thread_id
        )

        # Mark task as done in transaction
        async with self.db.session_maker() as session, session.begin():
            task_repo = TaskRepository(session)
            result = await task_repo.update_status(task_id, "done", version, message)

        if not result:
            logger.warning(f"Task {task_id} update failed: version conflict")
            return

        # Send result to user
        await self.notifier.notify_success(chat_id, thread_id, message)

    async def process_get_code(
        self,
        task_id: str,
        chat_id: int,
        thread_id: int,
        payload: dict,
        version: int,
    ) -> None:
        """
        Process get_code task.

        Args:
            task_id: Task ID string
            chat_id: Telegram chat_id
            thread_id: Telegram thread_id
            payload: Task payload with 'auth_url' field
            version: Task version for optimistic locking
        """
        auth_url = payload.get("auth_url")
        if not auth_url:
            raise TaskError("Missing 'auth_url' in payload")

        # Extract authorization code
        code = await self.playwright.extract_authorization_code(
            chat_id, auth_url, thread_id
        )

        # Update last_used and mark task as done in transaction
        async with self.db.session_maker() as session, session.begin():
            session_repo = ChatSessionRepository(session)
            await session_repo.update_last_used(chat_id, thread_id)

            task_repo = TaskRepository(session)
            result = await task_repo.update_status(task_id, "done", version, code)

        if not result:
            logger.warning(f"Task {task_id} update failed: version conflict")
            return

        # Send code to user
        await self.notifier.notify_success(
            chat_id, thread_id, f"✅ Authorization code: `{code}`"
        )

    async def _recovery_loop(self) -> None:
        """
        Background loop for recovering stuck tasks.

        Periodically checks for tasks stuck in 'processing' status
        and resets them to 'pending' for retry.
        """
        logger.info(
            f"Starting stuck task recovery loop "
            f"(interval: {self.settings.TASK_RECOVERY_INTERVAL}s, "
            f"timeout: {self.settings.TASK_STUCK_TIMEOUT}min)"
        )

        while self.running:
            try:
                await asyncio.sleep(self.settings.TASK_RECOVERY_INTERVAL)

                if not self.running:
                    break

                # Recover stuck tasks in transaction
                async with self.db.session_maker() as session, session.begin():
                    task_repo = TaskRepository(session)
                    recovered = await task_repo.recover_stuck_tasks(
                        self.settings.TASK_STUCK_TIMEOUT
                    )

                if recovered > 0:
                    logger.info(f"Recovery check: recovered {recovered} stuck tasks")

            except asyncio.CancelledError:
                logger.info("Recovery loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in recovery loop: {e}", exc_info=True)
                # Continue running even if recovery fails
                await asyncio.sleep(self.settings.TASK_RECOVERY_INTERVAL)
