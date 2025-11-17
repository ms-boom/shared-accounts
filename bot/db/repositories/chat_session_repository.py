"""Repository for ChatSession model database operations."""

import logging
from datetime import datetime

from databases import Database

from bot.core.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class ChatSessionRepository:
    """Repository pattern for ChatSession model operations."""

    def __init__(self, database: Database):
        """
        Initialize repository.

        Args:
            database: Database connection instance
        """
        self.db = database

    async def get_by_chat_id(self, chat_id: int) -> dict | None:
        """
        Get chat session by chat_id.

        Args:
            chat_id: Telegram chat_id

        Returns:
            ChatSession data as dict or None if not found

        Raises:
            DatabaseError: If database query fails
        """
        query = """
            SELECT chat_id, email, session_path, created_at, last_used
            FROM chat_sessions
            WHERE chat_id = :chat_id
        """
        try:
            result = await self.db.fetch_one(query, {"chat_id": chat_id})
            return dict(result) if result else None
        except Exception as e:
            logger.error("Failed to get chat session for %s: %s", chat_id, e)
            raise DatabaseError(f"Failed to get chat session: {e}") from e

    async def create(
        self,
        chat_id: int,
        email: str,
        session_path: str,
    ) -> dict:
        """
        Create a new chat session record.

        Args:
            chat_id: Telegram chat_id
            email: Email address for Claude account
            session_path: Path to Playwright session data

        Returns:
            Created chat session data as dict

        Raises:
            DatabaseError: If database operation fails
        """
        query = """
            INSERT INTO chat_sessions (chat_id, email, session_path, created_at)
            VALUES (:chat_id, :email, :session_path, :created_at)
            RETURNING chat_id, email, session_path, created_at, last_used
        """
        now = datetime.utcnow()
        values = {
            "chat_id": chat_id,
            "email": email,
            "session_path": session_path,
            "created_at": now,
        }

        try:
            result = await self.db.fetch_one(query, values)
            logger.info("Created chat session for %s (%s)", chat_id, email)
            return dict(result) if result else values
        except Exception as e:
            logger.error("Failed to create chat session for %s: %s", chat_id, e)
            raise DatabaseError(f"Failed to create chat session: {e}") from e

    async def update_last_used(self, chat_id: int) -> dict | None:
        """
        Update last_used timestamp for a chat session.

        Args:
            chat_id: Telegram chat_id

        Returns:
            Updated chat session data as dict or None if not found

        Raises:
            DatabaseError: If database operation fails
        """
        query = """
            UPDATE chat_sessions
            SET last_used = :last_used
            WHERE chat_id = :chat_id
            RETURNING chat_id, email, session_path, created_at, last_used
        """
        values = {
            "chat_id": chat_id,
            "last_used": datetime.utcnow(),
        }

        try:
            result = await self.db.fetch_one(query, values)
            if result:
                logger.info("Updated last_used for chat session %s", chat_id)
            return dict(result) if result else None
        except Exception as e:
            logger.error("Failed to update last_used for %s: %s", chat_id, e)
            raise DatabaseError(f"Failed to update last_used: {e}") from e

    async def delete(self, chat_id: int) -> bool:
        """
        Delete a chat session.

        Args:
            chat_id: Telegram chat_id

        Returns:
            True if deleted, False if not found

        Raises:
            DatabaseError: If database operation fails
        """
        query = """
            DELETE FROM chat_sessions
            WHERE chat_id = :chat_id
        """
        try:
            await self.db.execute(query, {"chat_id": chat_id})
            logger.info("Deleted chat session for %s", chat_id)
            return True
        except Exception as e:
            logger.error("Failed to delete chat session for %s: %s", chat_id, e)
            raise DatabaseError(f"Failed to delete chat session: {e}") from e

    async def upsert(
        self,
        chat_id: int,
        email: str,
        session_path: str,
    ) -> dict:
        """
        Insert or update a chat session (handles concurrent initialization).

        Args:
            chat_id: Telegram chat_id
            email: Email address for Claude account
            session_path: Path to Playwright session data

        Returns:
            Created or updated chat session data as dict

        Raises:
            DatabaseError: If database operation fails
        """
        query = """
            INSERT INTO chat_sessions (chat_id, email, session_path, created_at)
            VALUES (:chat_id, :email, :session_path, :created_at)
            ON CONFLICT (chat_id)
            DO UPDATE SET
                email = EXCLUDED.email,
                session_path = EXCLUDED.session_path
            RETURNING chat_id, email, session_path, created_at, last_used
        """
        now = datetime.utcnow()
        values = {
            "chat_id": chat_id,
            "email": email,
            "session_path": session_path,
            "created_at": now,
        }

        try:
            result = await self.db.fetch_one(query, values)
            logger.info("Upserted chat session for %s (%s)", chat_id, email)
            return dict(result) if result else values
        except Exception as e:
            logger.error("Failed to upsert chat session for %s: %s", chat_id, e)
            raise DatabaseError(f"Failed to upsert chat session: {e}") from e

    async def lock_for_update(self, chat_id: int) -> dict | None:
        """
        Lock chat session for update (prevents concurrent initialization).

        Args:
            chat_id: Telegram chat_id

        Returns:
            Locked chat session data as dict or None if not found

        Raises:
            DatabaseError: If database operation fails

        Note:
            Must be called within a transaction.
            Other transactions will wait or skip (SKIP LOCKED) this row.
        """
        query = """
            SELECT chat_id, email, session_path, created_at, last_used
            FROM chat_sessions
            WHERE chat_id = :chat_id
            FOR UPDATE
        """
        try:
            result = await self.db.fetch_one(query, {"chat_id": chat_id})
            return dict(result) if result else None
        except Exception as e:
            logger.error("Failed to lock chat session %s: %s", chat_id, e)
            raise DatabaseError(f"Failed to lock chat session: {e}") from e

    async def get_all_active(self) -> list[dict]:
        """
        Get all active chat sessions.

        Returns:
            List of all active chat sessions as dicts

        Raises:
            DatabaseError: If database query fails
        """
        query = """
            SELECT chat_id, email, session_path, created_at, last_used
            FROM chat_sessions
            ORDER BY last_used DESC NULLS LAST, created_at DESC
        """
        try:
            results = await self.db.fetch_all(query)
            return [dict(row) for row in results]
        except Exception as e:
            logger.error("Failed to get all chat sessions: %s", e)
            raise DatabaseError(f"Failed to get all chat sessions: {e}") from e
