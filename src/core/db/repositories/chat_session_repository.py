"""Repository for ChatSession model database operations.

Pattern from statements/ - repository accepts session, doesn't manage transactions.
"""

import logging
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import ChatSession
from core.exceptions import DatabaseError

logger = logging.getLogger(__name__)


def _row_to_dict(session: ChatSession) -> dict:
    """Convert ChatSession model to dict for backward compatibility."""
    return {
        "chat_id": session.chat_id,
        "thread_id": session.thread_id,
        "email": session.email,
        "session_path": session.session_path,
        "created_at": session.created_at,
        "last_used": session.last_used,
    }


class ChatSessionRepository:
    """Repository pattern for ChatSession model operations.

    Pattern from statements/ - accepts session, uses flush() not commit().
    Transaction management is handled by caller (use case or test).
    """

    def __init__(self, session: AsyncSession):
        """Initialize repository with session injection.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def get_by_chat_id(self, chat_id: int, thread_id: int = 0) -> dict | None:
        """Get chat session by chat_id and thread_id.

        Args:
            chat_id: Telegram chat_id
            thread_id: Telegram thread_id (0 for main chat, >0 for topics)

        Returns:
            ChatSession data as dict or None if not found

        Raises:
            DatabaseError: If database query fails
        """
        try:
            stmt = sa.select(ChatSession).where(
                ChatSession.chat_id == chat_id, ChatSession.thread_id == thread_id
            )
            result = await self.session.execute(stmt)
            session_obj = result.scalar_one_or_none()
            return _row_to_dict(session_obj) if session_obj else None
        except Exception as e:
            logger.error(f"Failed to get chat session for {chat_id}/{thread_id}: {e}")
            raise DatabaseError(f"Failed to get chat session: {e}") from e

    async def create(
        self,
        chat_id: int,
        email: str,
        session_path: str,
        thread_id: int = 0,
    ) -> dict:
        """
        Create a new chat session record.

        Args:
            chat_id: Telegram chat_id
            email: Email address for Claude account
            session_path: Path to Playwright session data
            thread_id: Telegram thread_id (0 for main chat, >0 for topics)

        Returns:
            Created chat session data as dict

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            session_obj = ChatSession(
                chat_id=chat_id,
                thread_id=thread_id,
                email=email,
                session_path=session_path,
                created_at=datetime.utcnow(),
            )
            self.session.add(session_obj)
            await self.session.flush()  # Not commit - transaction managed by caller
            logger.info(f"Created chat session for {chat_id}/{thread_id} ({email})")
            return _row_to_dict(session_obj)
        except Exception as e:
            logger.error(
                f"Failed to create chat session for {chat_id}/{thread_id}: {e}"
            )
            raise DatabaseError(f"Failed to create chat session: {e}") from e

    async def update_last_used(self, chat_id: int, thread_id: int = 0) -> dict | None:
        """
        Update last_used timestamp for a chat session.

        Args:
            chat_id: Telegram chat_id
            thread_id: Telegram thread_id (0 for main chat, >0 for topics)

        Returns:
            Updated chat session data as dict or None if not found

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            stmt = (
                sa.update(ChatSession)
                .where(
                    ChatSession.chat_id == chat_id,
                    ChatSession.thread_id == thread_id,
                )
                .values(last_used=datetime.utcnow())
                .returning(ChatSession)
            )
            result = await self.session.execute(stmt)
            await self.session.flush()
            session_obj = result.scalar_one_or_none()

            if session_obj:
                logger.info(f"Updated last_used for chat session {chat_id}/{thread_id}")
                return _row_to_dict(session_obj)
            return None
        except Exception as e:
            logger.error(f"Failed to update last_used for {chat_id}/{thread_id}: {e}")
            raise DatabaseError(f"Failed to update last_used: {e}") from e

    async def delete(self, chat_id: int, thread_id: int = 0) -> bool:
        """
        Delete a chat session.

        Args:
            chat_id: Telegram chat_id
            thread_id: Telegram thread_id (0 for main chat, >0 for topics)

        Returns:
            True if deleted, False if not found

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            stmt = sa.delete(ChatSession).where(
                ChatSession.chat_id == chat_id,
                ChatSession.thread_id == thread_id,
            )
            await self.session.execute(stmt)
            await self.session.flush()
            logger.info(f"Deleted chat session for {chat_id}/{thread_id}")
            return True
        except Exception as e:
            logger.error(
                f"Failed to delete chat session for {chat_id}/{thread_id}: {e}"
            )
            raise DatabaseError(f"Failed to delete chat session: {e}") from e

    async def upsert(
        self,
        chat_id: int,
        email: str,
        session_path: str,
        thread_id: int = 0,
    ) -> dict:
        """
        Insert or update a chat session (handles concurrent initialization).

        Args:
            chat_id: Telegram chat_id
            email: Email address for Claude account
            session_path: Path to Playwright session data
            thread_id: Telegram thread_id (0 for main chat, >0 for topics)

        Returns:
            Created or updated chat session data as dict

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            stmt = (
                sqlite_insert(ChatSession)
                .values(
                    chat_id=chat_id,
                    thread_id=thread_id,
                    email=email,
                    session_path=session_path,
                    created_at=datetime.utcnow(),
                )
                .on_conflict_do_update(
                    index_elements=["chat_id", "thread_id"],
                    set_={"email": email, "session_path": session_path},
                )
                .returning(ChatSession)
            )

            result = await self.session.execute(stmt)
            await self.session.flush()
            session_obj = result.scalar_one()

            logger.info(f"Upserted chat session for {chat_id}/{thread_id} ({email})")
            return _row_to_dict(session_obj)
        except Exception as e:
            logger.error(
                f"Failed to upsert chat session for {chat_id}/{thread_id}: {e}"
            )
            raise DatabaseError(f"Failed to upsert chat session: {e}") from e

    async def get_all_active(self) -> list[dict]:
        """
        Get all active chat sessions.

        Returns:
            List of all active chat sessions as dicts

        Raises:
            DatabaseError: If database query fails
        """
        try:
            stmt = sa.select(ChatSession).order_by(
                ChatSession.last_used.desc().nulls_last(),
                ChatSession.created_at.desc(),
            )
            result = await self.session.execute(stmt)
            sessions = result.scalars().all()
            return [_row_to_dict(session) for session in sessions]
        except Exception as e:
            logger.error(f"Failed to get all chat sessions: {e}")
            raise DatabaseError(f"Failed to get all chat sessions: {e}") from e
