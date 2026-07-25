"""Ownership checks for the fingerprint feature — private / group-admin / shared-edit.

Presentation-layer service: needs `Bot` for `get_chat_member` (via the cached
`PermissionService`), so it lives in `src/bot/`, not `src/core/`.
"""

import logging

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.permission_service import PermissionService
from core.db.repositories.fingerprint_repository import FingerprintRepository
from core.db.repositories.session_fingerprint_repository import (
    SessionFingerprintRepository,
)

logger = logging.getLogger(__name__)


class FingerprintAccessService:
    """Decides who may view/edit a fingerprint binding.

    Private session (`chat_id > 0`): owned iff `chat_id == user_id`. Group
    session (`chat_id < 0`): owned iff the user is a group admin (cached via
    `PermissionService`). Topic threads (`thread_id > 0`) exist only in
    groups, where the private shortcut can never match.
    """

    def __init__(self, permission_service: PermissionService) -> None:
        """Initialize service.

        Args:
            permission_service: cached admin-status checker
        """
        self.permission_service = permission_service

    async def is_owned(
        self, bot: Bot, user_id: int, chat_id: int, thread_id: int = 0
    ) -> bool:
        """Check whether `user_id` owns the fingerprint binding at (chat_id, thread_id).

        Args:
            bot: Bot instance (for `get_chat_member` in the group case)
            user_id: Telegram user_id requesting access
            chat_id: Telegram chat_id of the session
            thread_id: Telegram thread_id (unused by the ownership rule itself;
                kept for call-site symmetry with the other fingerprint methods)

        Returns:
            True if the user owns this session's fingerprint binding
        """
        if chat_id > 0:
            return chat_id == user_id
        return await self.permission_service.is_group_admin(bot, user_id, chat_id)

    async def list_owned_sources(
        self, session: AsyncSession, bot: Bot, user_id: int
    ) -> list[dict]:
        """List every fingerprint-bound session owned by `user_id`.

        Args:
            session: read session
            bot: Bot instance (for ownership checks on group bindings)
            user_id: Telegram user_id requesting the list

        Returns:
            Owned bindings, each carrying chat_id/thread_id + the bound
            fingerprint's label and values, for the copy-source picker
        """
        bindings = await SessionFingerprintRepository(session).list_all()

        owned_bindings: list[dict] = []
        for binding in bindings:
            owned = await self.is_owned(
                bot, user_id, binding["chat_id"], binding["thread_id"]
            )
            if owned:
                owned_bindings.append(binding)

        fingerprints = await FingerprintRepository(session).get_many(
            [binding["fingerprint_id"] for binding in owned_bindings]
        )

        return [
            _source_entry(binding, fingerprints.get(binding["fingerprint_id"]))
            for binding in owned_bindings
        ]

    async def can_edit_fingerprint(
        self, session: AsyncSession, bot: Bot, user_id: int, fingerprint_id: int
    ) -> bool:
        """Check whether `user_id` may edit a (possibly shared) fingerprint.

        True iff the user owns at least one session bound to it (decision:
        cross-group edit of a shared fingerprint is allowed per-binding-owner).

        Args:
            session: read session
            bot: Bot instance (for ownership checks)
            user_id: Telegram user_id requesting edit access
            fingerprint_id: fingerprint id to check

        Returns:
            True if the user owns at least one bound session
        """
        bindings = await SessionFingerprintRepository(session).list_for_fingerprint(
            fingerprint_id
        )
        for binding in bindings:
            if await self.is_owned(
                bot, user_id, binding["chat_id"], binding["thread_id"]
            ):
                return True
        return False


def _source_entry(binding: dict, fingerprint: dict | None) -> dict:
    """Flatten a binding + its fingerprint row into one picker-ready dict."""
    return {
        "chat_id": binding["chat_id"],
        "thread_id": binding["thread_id"],
        "fingerprint_id": binding["fingerprint_id"],
        "label": fingerprint["label"] if fingerprint else None,
        "user_agent": fingerprint["user_agent"] if fingerprint else None,
        "cpu_cores": fingerprint["cpu_cores"] if fingerprint else None,
        "device_memory": fingerprint["device_memory"] if fingerprint else None,
        "timezone": fingerprint["timezone"] if fingerprint else None,
        "locale": fingerprint["locale"] if fingerprint else None,
    }
