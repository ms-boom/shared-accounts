"""WRITE-side fingerprint service — bind/rebind/edit + the single orphan-cleanup rule.

Methods accept a `session` and manage no transaction: the caller wraps each
call in `database.write(fn)`, so a single operation (create/bind/cleanup) is
atomic and serialized through `SQLiteWriterQueue`.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from core.db.repositories.fingerprint_repository import FingerprintRepository
from core.db.repositories.session_fingerprint_repository import (
    SessionFingerprintRepository,
)
from core.exceptions import FingerprintNotFoundError
from core.fingerprint import FingerprintValues, build_label

logger = logging.getLogger(__name__)


class FingerprintManagementService:
    """Coordinates `FingerprintRepository` + `SessionFingerprintRepository`.

    Owns the single orphan-cleanup rule (`_cleanup_if_orphan`): a fingerprint
    with zero remaining bindings is deleted synchronously, in the same write.
    """

    async def set_own(
        self,
        session: AsyncSession,
        chat_id: int,
        thread_id: int,
        *,
        values: FingerprintValues,
        created_by: int,
    ) -> int:
        """Create a fresh fingerprint for this session only, then bind it.

        Also the "detach & set own" path for a session currently sharing a
        fingerprint: the old binding is replaced and cleaned up if orphaned.

        Args:
            session: write-scoped session
            chat_id: Telegram chat_id
            thread_id: Telegram thread_id (0 for main chat, >0 for topics)
            values: the five (possibly partial) fingerprint fields
            created_by: Telegram user_id creating this profile (audit only)

        Returns:
            The id of the newly created fingerprint
        """
        session_fp_repo = SessionFingerprintRepository(session)
        old_binding = await session_fp_repo.get(chat_id, thread_id)

        created = await FingerprintRepository(session).create(
            values=values, label=build_label(values), created_by=created_by
        )
        fingerprint_id = created["id"]

        await session_fp_repo.bind(chat_id, thread_id, fingerprint_id)

        if old_binding is not None:
            await self._cleanup_if_orphan(session, old_binding["fingerprint_id"])

        return int(fingerprint_id)

    async def copy_from(
        self,
        session: AsyncSession,
        chat_id: int,
        thread_id: int,
        *,
        source_fingerprint_id: int,
    ) -> None:
        """Bind a session to an existing fingerprint (shared-by-reference).

        Args:
            session: write-scoped session
            chat_id: Telegram chat_id
            thread_id: Telegram thread_id (0 for main chat, >0 for topics)
            source_fingerprint_id: fingerprint id to share
        """
        session_fp_repo = SessionFingerprintRepository(session)
        old_binding = await session_fp_repo.get(chat_id, thread_id)

        await session_fp_repo.bind(chat_id, thread_id, source_fingerprint_id)

        if (
            old_binding is not None
            and old_binding["fingerprint_id"] != source_fingerprint_id
        ):
            await self._cleanup_if_orphan(session, old_binding["fingerprint_id"])

    async def edit_shared(
        self,
        session: AsyncSession,
        fingerprint_id: int,
        *,
        values: FingerprintValues,
        label: str | None,
    ) -> None:
        """Overwrite a fingerprint's values/label — affects every bound session.

        Args:
            session: write-scoped session
            fingerprint_id: fingerprint id to edit
            values: the five (possibly partial) fingerprint fields, full replace
            label: new display label

        Raises:
            FingerprintNotFoundError: if the fingerprint no longer exists (the
                stale-menu race: it was deleted by orphan-cleanup between the
                caller reading it and this write)
        """
        updated = await FingerprintRepository(session).update_values(
            fingerprint_id, values, label
        )
        if updated is None:
            raise FingerprintNotFoundError(f"Fingerprint {fingerprint_id} not found")

    async def reset(self, session: AsyncSession, chat_id: int, thread_id: int) -> bool:
        """Unbind a session and clean up its fingerprint if now orphaned.

        Args:
            session: write-scoped session
            chat_id: Telegram chat_id
            thread_id: Telegram thread_id (0 for main chat, >0 for topics)

        Returns:
            True if a binding was removed, False if the session was already unbound
        """
        session_fp_repo = SessionFingerprintRepository(session)
        old_binding = await session_fp_repo.get(chat_id, thread_id)
        if old_binding is None:
            return False

        await session_fp_repo.unbind(chat_id, thread_id)
        await self._cleanup_if_orphan(session, old_binding["fingerprint_id"])
        return True

    async def _cleanup_if_orphan(
        self, session: AsyncSession, fingerprint_id: int
    ) -> None:
        """Delete a fingerprint iff it has zero remaining bindings.

        Single source of truth for the orphan-cleanup rule: called after every
        binding move (reset / detach-and-set-own / copy that replaces a
        previous binding).

        Args:
            session: write-scoped session
            fingerprint_id: fingerprint id to check
        """
        remaining = await SessionFingerprintRepository(session).count_for_fingerprint(
            fingerprint_id
        )
        if remaining == 0:
            await FingerprintRepository(session).delete(fingerprint_id)
            logger.info(f"Deleted orphaned fingerprint {fingerprint_id}")
