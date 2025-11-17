"""Repository for Task model database operations."""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from databases import Database

from bot.core.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class TaskRepository:
    """Repository pattern for Task model operations."""

    def __init__(self, database: Database):
        """
        Initialize repository.

        Args:
            database: Database connection instance
        """
        self.db = database

    async def get_by_id(self, task_id: UUID) -> dict | None:
        """
        Get task by ID.

        Args:
            task_id: Task UUID

        Returns:
            Task data as dict or None if not found

        Raises:
            DatabaseError: If database query fails
        """
        query = """
            SELECT id, chat_id, user_id, task_type, payload, status,
                   result, created_at, updated_at
            FROM tasks
            WHERE id = :task_id
        """
        try:
            result = await self.db.fetch_one(query, {"task_id": str(task_id)})
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Failed to get task {task_id}: {e}")
            raise DatabaseError(f"Failed to get task: {e}") from e

    async def create(
        self,
        chat_id: int,
        user_id: int,
        task_type: str,
        payload: dict[str, Any],
    ) -> dict:
        """
        Create a new task.

        Args:
            chat_id: Telegram chat_id
            user_id: Telegram user_id who initiated task
            task_type: Task type ('init_session' or 'get_code')
            payload: Task-specific payload

        Returns:
            Created task data as dict

        Raises:
            DatabaseError: If database operation fails
        """
        query = """
            INSERT INTO tasks (chat_id, user_id, task_type, payload, status, created_at, updated_at)
            VALUES (:chat_id, :user_id, :task_type, :payload, :status, :created_at, :updated_at)
            RETURNING id, chat_id, user_id, task_type, payload, status,
                      result, created_at, updated_at
        """
        now = datetime.utcnow()
        values = {
            "chat_id": chat_id,
            "user_id": user_id,
            "task_type": task_type,
            "payload": payload,
            "status": "pending",
            "created_at": now,
            "updated_at": now,
        }

        try:
            result = await self.db.fetch_one(query, values)
            if result is None:
                raise DatabaseError("INSERT RETURNING returned None")
            logger.info(f"Created task {result['id']} for chat {chat_id}")
            return dict(result)
        except Exception as e:
            logger.error(f"Failed to create task for chat {chat_id}: {e}")
            raise DatabaseError(f"Failed to create task: {e}") from e

    async def update_status(
        self,
        task_id: UUID,
        status: str,
        result: str | None = None,
    ) -> dict | None:
        """
        Update task status and result.

        Args:
            task_id: Task UUID
            status: New status ('processing', 'done', 'failed')
            result: Task result or error message

        Returns:
            Updated task data as dict or None if not found

        Raises:
            DatabaseError: If database operation fails
        """
        query = """
            UPDATE tasks
            SET status = :status,
                result = :result,
                updated_at = :updated_at
            WHERE id = :task_id
            RETURNING id, chat_id, user_id, task_type, payload, status,
                      result, created_at, updated_at
        """
        values = {
            "task_id": str(task_id),
            "status": status,
            "result": result,
            "updated_at": datetime.utcnow(),
        }

        try:
            result_row = await self.db.fetch_one(query, values)
            if result_row:
                logger.info(f"Updated task {task_id} status to {status}")
            return dict(result_row) if result_row else None
        except Exception as e:
            logger.error(f"Failed to update task {task_id}: {e}")
            raise DatabaseError(f"Failed to update task: {e}") from e

    async def dequeue_pending_task(self) -> dict | None:
        """
        Dequeue next pending task and mark it as processing.

        Uses SELECT FOR UPDATE SKIP LOCKED for safe concurrent processing.

        Returns:
            Task data as dict or None if no pending tasks

        Raises:
            DatabaseError: If database operation fails

        Note:
            Must be called within a transaction.
        """
        # First, select and lock the next pending task
        select_query = """
            SELECT id, chat_id, user_id, task_type, payload, status,
                   result, created_at, updated_at
            FROM tasks
            WHERE status = 'pending'
            ORDER BY created_at ASC
            FOR UPDATE SKIP LOCKED
            LIMIT 1
        """

        try:
            task = await self.db.fetch_one(select_query)
            if not task:
                return None

            # Mark task as processing
            update_query = """
                UPDATE tasks
                SET status = 'processing',
                    updated_at = :updated_at
                WHERE id = :task_id
                RETURNING id, chat_id, user_id, task_type, payload, status,
                          result, created_at, updated_at
            """
            values = {
                "task_id": task["id"],
                "updated_at": datetime.utcnow(),
            }

            result = await self.db.fetch_one(update_query, values)
            if result:
                logger.info(f"Dequeued task {result['id']} for processing")
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Failed to dequeue pending task: {e}")
            raise DatabaseError(f"Failed to dequeue pending task: {e}") from e

    async def get_pending_count(self) -> int:
        """
        Get count of pending tasks.

        Returns:
            Number of pending tasks

        Raises:
            DatabaseError: If database query fails
        """
        query = """
            SELECT COUNT(*) as count
            FROM tasks
            WHERE status = 'pending'
        """
        try:
            result = await self.db.fetch_one(query)
            return result["count"] if result else 0
        except Exception as e:
            logger.error(f"Failed to get pending task count: {e}")
            raise DatabaseError(f"Failed to get pending task count: {e}") from e

    async def get_by_chat_id(
        self,
        chat_id: int,
        limit: int = 10,
    ) -> list[dict]:
        """
        Get tasks for a specific chat.

        Args:
            chat_id: Telegram chat_id
            limit: Maximum number of tasks to return

        Returns:
            List of tasks as dicts

        Raises:
            DatabaseError: If database query fails
        """
        query = """
            SELECT id, chat_id, user_id, task_type, payload, status,
                   result, created_at, updated_at
            FROM tasks
            WHERE chat_id = :chat_id
            ORDER BY created_at DESC
            LIMIT :limit
        """
        try:
            results = await self.db.fetch_all(
                query, {"chat_id": chat_id, "limit": limit}
            )
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Failed to get tasks for chat {chat_id}: {e}")
            raise DatabaseError(f"Failed to get tasks for chat: {e}") from e
