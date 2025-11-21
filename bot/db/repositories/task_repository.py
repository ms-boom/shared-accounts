"""Repository for Task model database operations.

Pattern from statements/ - repository accepts session, doesn't manage transactions.
"""

import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.exceptions import DatabaseError
from bot.db.models import Task

logger = logging.getLogger(__name__)


def _row_to_dict(task: Task) -> dict:
    """Convert Task model to dict for backward compatibility."""
    return {
        "id": task.id,
        "chat_id": task.chat_id,
        "thread_id": task.thread_id,
        "user_id": task.user_id,
        "task_type": task.task_type,
        "payload": task.payload,
        "status": task.status,
        "result": task.result,
        "version": task.version,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


class TaskRepository:
    """Repository pattern for Task model operations.

    Pattern from statements/ - accepts session, uses flush() not commit().
    Transaction management is handled by caller (use case or test).
    """

    def __init__(self, session: AsyncSession):
        """Initialize repository with session injection.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def get_by_id(self, task_id: UUID) -> dict | None:
        """Get task by ID.

        Args:
            task_id: Task UUID

        Returns:
            Task data as dict or None if not found

        Raises:
            DatabaseError: If database query fails
        """
        try:
            stmt = sa.select(Task).where(Task.id == task_id)
            result = await self.session.execute(stmt)
            task = result.scalar_one_or_none()
            return _row_to_dict(task) if task else None
        except Exception as e:
            logger.error(f"Failed to get task {task_id}: {e}")
            raise DatabaseError(f"Failed to get task: {e}") from e

    async def create(
        self,
        chat_id: int,
        user_id: int,
        task_type: str,
        payload: dict[str, Any],
        thread_id: int = 0,
    ) -> dict:
        """Create a new task.

        Args:
            chat_id: Telegram chat_id
            user_id: Telegram user_id who initiated task
            task_type: Task type ('init_session' or 'get_code')
            payload: Task-specific payload
            thread_id: Telegram thread_id (0 for main chat, >0 for topics)

        Returns:
            Created task data as dict

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            task = Task(
                chat_id=chat_id,
                thread_id=thread_id,
                user_id=user_id,
                task_type=task_type,
                payload=payload,
                status="pending",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            self.session.add(task)
            await self.session.flush()  # Not commit - transaction managed by caller
            logger.info(f"Created task {task.id} for chat {chat_id}/{thread_id}")
            return _row_to_dict(task)
        except Exception as e:
            logger.error(f"Failed to create task for chat {chat_id}/{thread_id}: {e}")
            raise DatabaseError(f"Failed to create task: {e}") from e

    async def update_status(
        self,
        task_id: UUID,
        status: str,
        expected_version: int,
        result: str | None = None,
    ) -> dict | None:
        """Update task status and result using optimistic locking.

        Args:
            task_id: Task UUID
            status: New status ('processing', 'done', 'failed')
            expected_version: Expected version for optimistic locking
            result: Task result or error message

        Returns:
            Updated task data as dict or None if version mismatch (conflict)

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            stmt = (
                sa.update(Task)
                .where(Task.id == task_id, Task.version == expected_version)
                .values(
                    status=status,
                    result=result,
                    version=Task.version + 1,
                    updated_at=datetime.utcnow(),
                )
                .returning(Task)
            )
            db_result = await self.session.execute(stmt)
            await self.session.flush()
            task = db_result.scalar_one_or_none()

            if task:
                logger.info(f"Updated task {task_id} status to {status}")
                return _row_to_dict(task)
            else:
                logger.warning(
                    f"Failed to update task {task_id}: version mismatch "
                    f"(expected {expected_version})"
                )
                return None
        except Exception as e:
            logger.error(f"Failed to update task {task_id}: {e}")
            raise DatabaseError(f"Failed to update task: {e}") from e

    async def dequeue_pending_task(self) -> dict | None:
        """Dequeue next pending task and mark it as processing.

        Uses SELECT FOR UPDATE with optimistic locking.
        PostgreSQL uses SKIP LOCKED for better concurrency.
        SQLite uses regular FOR UPDATE (less concurrent but simpler).

        Returns:
            Task data as dict or None if no pending tasks

        Raises:
            DatabaseError: If database operation fails

        Note:
            Must be called within a transaction.
            Uses pessimistic locking to prevent race conditions.
        """
        try:
            # Detect database type from session bind
            dialect_name = (
                self.session.bind.dialect.name if self.session.bind else "sqlite"
            )

            # Select and lock the next pending task
            stmt = (
                sa.select(Task)
                .where(Task.status == "pending")
                .order_by(Task.created_at.asc())
                .limit(1)
            )

            # PostgreSQL supports SKIP LOCKED for better concurrency
            if dialect_name == "postgresql":
                stmt = stmt.with_for_update(skip_locked=True)
            else:
                # SQLite doesn't support SKIP LOCKED, use regular FOR UPDATE
                stmt = stmt.with_for_update()

            result = await self.session.execute(stmt)
            task = result.scalar_one_or_none()

            if not task:
                return None

            # Mark task as processing and increment version
            task.status = "processing"
            task.version = task.version + 1
            task.updated_at = datetime.utcnow()

            await self.session.flush()
            logger.info(f"Dequeued task {task.id} for processing")
            return _row_to_dict(task)
        except Exception as e:
            # SQLite may raise OperationalError if row is locked
            # In this case, just return None (task was taken by another worker)
            if "locked" in str(e).lower():
                logger.debug("Task is locked by another worker, skipping")
                return None
            logger.error(f"Failed to dequeue pending task: {e}")
            raise DatabaseError(f"Failed to dequeue pending task: {e}") from e

    async def get_pending_count(self) -> int:
        """Get count of pending tasks.

        Returns:
            Number of pending tasks

        Raises:
            DatabaseError: If database query fails
        """
        try:
            stmt = (
                sa.select(sa.func.count())
                .select_from(Task)
                .where(Task.status == "pending")
            )
            result = await self.session.execute(stmt)
            count = result.scalar()
            return count if count is not None else 0
        except Exception as e:
            logger.error(f"Failed to get pending task count: {e}")
            raise DatabaseError(f"Failed to get pending task count: {e}") from e

    async def get_by_chat_id(
        self,
        chat_id: int,
        limit: int = 10,
        thread_id: int | None = None,
    ) -> list[dict]:
        """Get tasks for a specific chat or topic.

        Args:
            chat_id: Telegram chat_id
            limit: Maximum number of tasks to return
            thread_id: Optional thread_id filter (None = all threads)

        Returns:
            List of tasks as dicts

        Raises:
            DatabaseError: If database query fails
        """
        try:
            stmt = sa.select(Task).where(Task.chat_id == chat_id)

            if thread_id is not None:
                stmt = stmt.where(Task.thread_id == thread_id)

            stmt = stmt.order_by(Task.created_at.desc()).limit(limit)

            result = await self.session.execute(stmt)
            tasks = result.scalars().all()
            return [_row_to_dict(task) for task in tasks]
        except Exception as e:
            logger.error(f"Failed to get tasks for chat {chat_id}: {e}")
            raise DatabaseError(f"Failed to get tasks for chat: {e}") from e

    async def recover_stuck_tasks(self, stuck_timeout_minutes: int = 5) -> int:
        """Recover tasks stuck in 'processing' status.

        Tasks in 'processing' status longer than stuck_timeout_minutes are reset to 'pending'.
        This handles cases where worker crashes or loses connection.

        Args:
            stuck_timeout_minutes: Minutes after which task is considered stuck

        Returns:
            Number of tasks recovered

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            timeout_threshold = datetime.utcnow() - timedelta(
                minutes=stuck_timeout_minutes
            )

            stmt = (
                sa.update(Task)
                .where(Task.status == "processing", Task.updated_at < timeout_threshold)
                .values(
                    status="pending",
                    version=Task.version + 1,
                    updated_at=datetime.utcnow(),
                )
                .returning(Task.id)
            )

            result = await self.session.execute(stmt)
            await self.session.flush()
            task_ids = [str(row[0]) for row in result.fetchall()]
            count = len(task_ids)

            if count > 0:
                logger.warning(
                    f"Recovered {count} stuck tasks: {', '.join(task_ids[:5])}"
                    + (f" and {count - 5} more" if count > 5 else "")
                )
            return count
        except Exception as e:
            logger.error(f"Failed to recover stuck tasks: {e}")
            raise DatabaseError(f"Failed to recover stuck tasks: {e}") from e
