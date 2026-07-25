"""Repository for SessionFingerprint model database operations.

Pattern from chat_session_repository.py - repository accepts session, doesn't
manage transactions.
"""

import logging
from typing import cast

import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import SessionFingerprint
from core.exceptions import DatabaseError

logger = logging.getLogger(__name__)


def _row_to_dict(binding: SessionFingerprint) -> dict:
    """Convert SessionFingerprint model to dict for backward compatibility."""
    return {
        "chat_id": binding.chat_id,
        "thread_id": binding.thread_id,
        "fingerprint_id": binding.fingerprint_id,
        "created_at": binding.created_at,
        "updated_at": binding.updated_at,
    }


class SessionFingerprintRepository:
    """Repository pattern for SessionFingerprint model operations.

    Accepts session, uses flush() not commit(). Transaction management is
    handled by the caller (service or test). A session has at most one
    binding, enforced by the composite `(chat_id, thread_id)` primary key.
    """

    def __init__(self, session: AsyncSession):
        """Initialize repository with session injection.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def get(self, chat_id: int, thread_id: int = 0) -> dict | None:
        """Get the fingerprint binding for a session.

        Args:
            chat_id: Telegram chat_id
            thread_id: Telegram thread_id (0 for main chat, >0 for topics)

        Returns:
            Binding data as dict or None if unbound

        Raises:
            DatabaseError: If database query fails
        """
        try:
            stmt = sa.select(SessionFingerprint).where(
                SessionFingerprint.chat_id == chat_id,
                SessionFingerprint.thread_id == thread_id,
            )
            result = await self.session.execute(stmt)
            binding = result.scalar_one_or_none()
            return _row_to_dict(binding) if binding else None
        except Exception as e:
            logger.error(
                f"Failed to get fingerprint binding for {chat_id}/{thread_id}: {e}"
            )
            raise DatabaseError(f"Failed to get fingerprint binding: {e}") from e

    async def bind(self, chat_id: int, thread_id: int, fingerprint_id: int) -> dict:
        """Bind a session to a fingerprint (upsert on the composite PK).

        A session's single binding is replaced if it already exists.

        Args:
            chat_id: Telegram chat_id
            thread_id: Telegram thread_id (0 for main chat, >0 for topics)
            fingerprint_id: target fingerprint id

        Returns:
            The binding data as dict

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            stmt = (
                sqlite_insert(SessionFingerprint)
                .values(
                    chat_id=chat_id,
                    thread_id=thread_id,
                    fingerprint_id=fingerprint_id,
                )
                .on_conflict_do_update(
                    index_elements=["chat_id", "thread_id"],
                    set_={"fingerprint_id": fingerprint_id},
                )
                .returning(SessionFingerprint)
            )
            result = await self.session.execute(stmt)
            await self.session.flush()
            binding = result.scalar_one()

            logger.info(f"Bound {chat_id}/{thread_id} to fingerprint {fingerprint_id}")
            return _row_to_dict(binding)
        except Exception as e:
            logger.error(
                f"Failed to bind {chat_id}/{thread_id} to fingerprint {fingerprint_id}: {e}"
            )
            raise DatabaseError(f"Failed to bind fingerprint: {e}") from e

    async def unbind(self, chat_id: int, thread_id: int = 0) -> bool:
        """Remove the fingerprint binding for a session.

        Args:
            chat_id: Telegram chat_id
            thread_id: Telegram thread_id (0 for main chat, >0 for topics)

        Returns:
            True if a binding was removed, False if there was none

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            stmt = sa.delete(SessionFingerprint).where(
                SessionFingerprint.chat_id == chat_id,
                SessionFingerprint.thread_id == thread_id,
            )
            result = await self.session.execute(stmt)
            await self.session.flush()
            # DELETE without RETURNING always yields a CursorResult (has rowcount).
            unbound = cast(CursorResult, result).rowcount > 0
            if unbound:
                logger.info(f"Unbound fingerprint from {chat_id}/{thread_id}")
            return unbound
        except Exception as e:
            logger.error(
                f"Failed to unbind fingerprint from {chat_id}/{thread_id}: {e}"
            )
            raise DatabaseError(f"Failed to unbind fingerprint: {e}") from e

    async def count_for_fingerprint(self, fingerprint_id: int) -> int:
        """Count sessions currently bound to a fingerprint.

        Uses the `ix_session_fingerprints_fingerprint_id` index — an index
        lookup, not a table scan.

        Args:
            fingerprint_id: target fingerprint id

        Returns:
            Number of bound sessions

        Raises:
            DatabaseError: If database query fails
        """
        try:
            stmt = (
                sa.select(sa.func.count())
                .select_from(SessionFingerprint)
                .where(SessionFingerprint.fingerprint_id == fingerprint_id)
            )
            result = await self.session.execute(stmt)
            return int(result.scalar_one())
        except Exception as e:
            logger.error(
                f"Failed to count sessions for fingerprint {fingerprint_id}: {e}"
            )
            raise DatabaseError(f"Failed to count sessions for fingerprint: {e}") from e

    async def list_for_fingerprint(self, fingerprint_id: int) -> list[dict]:
        """List every session bound to a fingerprint.

        Args:
            fingerprint_id: target fingerprint id

        Returns:
            List of binding dicts

        Raises:
            DatabaseError: If database query fails
        """
        try:
            stmt = sa.select(SessionFingerprint).where(
                SessionFingerprint.fingerprint_id == fingerprint_id
            )
            result = await self.session.execute(stmt)
            bindings = result.scalars().all()
            return [_row_to_dict(binding) for binding in bindings]
        except Exception as e:
            logger.error(
                f"Failed to list sessions for fingerprint {fingerprint_id}: {e}"
            )
            raise DatabaseError(f"Failed to list sessions for fingerprint: {e}") from e

    async def list_all(self) -> list[dict]:
        """List every fingerprint binding.

        Returns:
            List of all binding dicts

        Raises:
            DatabaseError: If database query fails
        """
        try:
            stmt = sa.select(SessionFingerprint)
            result = await self.session.execute(stmt)
            bindings = result.scalars().all()
            return [_row_to_dict(binding) for binding in bindings]
        except Exception as e:
            logger.error(f"Failed to list all fingerprint bindings: {e}")
            raise DatabaseError(f"Failed to list all fingerprint bindings: {e}") from e
