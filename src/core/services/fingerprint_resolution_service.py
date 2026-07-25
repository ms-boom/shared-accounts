"""READ-side fingerprint service — the single per-field merge definition."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings
from core.db.repositories.fingerprint_repository import FingerprintRepository
from core.db.repositories.session_fingerprint_repository import (
    SessionFingerprintRepository,
)
from core.fingerprint import EffectiveFingerprint, FingerprintValues, FingerprintView

logger = logging.getLogger(__name__)

_FIELDS = ("user_agent", "cpu_cores", "device_memory", "timezone", "locale")


class FingerprintResolutionService:
    """Resolves the effective, fully-populated fingerprint for a session.

    `merge` is the single place where the per-field fallback (stored value or
    default) is decided — every other path (`resolve`, `resolve_view`) routes
    through it so behaviour and the `/fingerprint` view card can never
    disagree.
    """

    def __init__(self, settings: Settings) -> None:
        """Build the immutable default profile once from the 5 `DEFAULT_*` settings.

        Args:
            settings: application settings carrying the `DEFAULT_*` fields
        """
        self._default = EffectiveFingerprint(
            user_agent=settings.DEFAULT_USER_AGENT,
            cpu_cores=settings.DEFAULT_CPU_CORES,
            device_memory=settings.DEFAULT_DEVICE_MEMORY,
            timezone=settings.DEFAULT_TIMEZONE,
            locale=settings.DEFAULT_LOCALE,
        )

    def default(self) -> EffectiveFingerprint:
        """Return the default profile (no binding / CLI shortcut).

        Returns:
            The immutable default `EffectiveFingerprint`
        """
        return self._default

    def merge(self, stored: FingerprintValues | None) -> EffectiveFingerprint:
        """Resolve stored (possibly partial) values against the default profile.

        Pure — the single per-field fallback definition: a `None` field falls
        back to the matching default field; `stored is None` returns the full
        default.

        Args:
            stored: possibly-partial stored values, or None if unbound

        Returns:
            A fully-populated `EffectiveFingerprint`
        """
        if stored is None:
            return self._default

        return EffectiveFingerprint(
            user_agent=stored.user_agent
            if stored.user_agent is not None
            else self._default.user_agent,
            cpu_cores=stored.cpu_cores
            if stored.cpu_cores is not None
            else self._default.cpu_cores,
            device_memory=stored.device_memory
            if stored.device_memory is not None
            else self._default.device_memory,
            timezone=stored.timezone
            if stored.timezone is not None
            else self._default.timezone,
            locale=stored.locale if stored.locale is not None else self._default.locale,
        )

    async def resolve(
        self, session: AsyncSession, chat_id: int, thread_id: int
    ) -> EffectiveFingerprint:
        """Resolve the effective fingerprint for a session.

        Args:
            session: read session
            chat_id: Telegram chat_id
            thread_id: Telegram thread_id (0 for main chat, >0 for topics)

        Returns:
            A fully-populated `EffectiveFingerprint`
        """
        binding = await SessionFingerprintRepository(session).get(chat_id, thread_id)
        if binding is None:
            return self.merge(None)

        values = await FingerprintRepository(session).get_values(
            binding["fingerprint_id"]
        )
        return self.merge(values)

    async def resolve_view(
        self, session: AsyncSession, chat_id: int, thread_id: int
    ) -> FingerprintView:
        """Build the display-ready view for the `/fingerprint` card.

        Args:
            session: read session
            chat_id: Telegram chat_id
            thread_id: Telegram thread_id (0 for main chat, >0 for topics)

        Returns:
            `FingerprintView` with the effective values, per-field source,
            shared-session count and label
        """
        binding = await SessionFingerprintRepository(session).get(chat_id, thread_id)
        if binding is None:
            return FingerprintView(
                effective=self.merge(None),
                source=dict.fromkeys(_FIELDS, "default"),
                shared_session_count=0,
                label=None,
            )

        fingerprint_id = binding["fingerprint_id"]
        fingerprint_row = await FingerprintRepository(session).get(fingerprint_id)
        stored_values = _row_to_values(fingerprint_row) if fingerprint_row else None
        shared_session_count = await SessionFingerprintRepository(
            session
        ).count_for_fingerprint(fingerprint_id)

        return FingerprintView(
            effective=self.merge(stored_values),
            source=_field_sources(stored_values),
            shared_session_count=shared_session_count,
            label=fingerprint_row["label"] if fingerprint_row else None,
        )


def _row_to_values(row: dict) -> FingerprintValues:
    """Extract the five value fields from a `FingerprintRepository.get()` row."""
    return FingerprintValues(
        user_agent=row["user_agent"],
        cpu_cores=row["cpu_cores"],
        device_memory=row["device_memory"],
        timezone=row["timezone"],
        locale=row["locale"],
    )


def _field_sources(stored: FingerprintValues | None) -> dict[str, str]:
    """Map each field to `"own"` (non-null stored override) or `"default"`."""
    if stored is None:
        return dict.fromkeys(_FIELDS, "default")
    return {
        field: "own" if getattr(stored, field) is not None else "default"
        for field in _FIELDS
    }
