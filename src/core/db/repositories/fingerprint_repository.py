"""Repository for Fingerprint model database operations.

Pattern from chat_session_repository.py - repository accepts session, doesn't
manage transactions.
"""

import logging
from typing import cast

import sqlalchemy as sa
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import Fingerprint
from core.exceptions import DatabaseError
from core.fingerprint import FingerprintValues

logger = logging.getLogger(__name__)


def _row_to_dict(fingerprint: Fingerprint) -> dict:
    """Convert Fingerprint model to dict for backward compatibility."""
    return {
        "id": fingerprint.id,
        "user_agent": fingerprint.user_agent,
        "cpu_cores": fingerprint.cpu_cores,
        "device_memory": fingerprint.device_memory,
        "timezone": fingerprint.timezone,
        "locale": fingerprint.locale,
        "label": fingerprint.label,
        "created_by": fingerprint.created_by,
        "created_at": fingerprint.created_at,
        "updated_at": fingerprint.updated_at,
    }


def _row_to_values(fingerprint: Fingerprint) -> FingerprintValues:
    """Extract the five nullable value fields as a `FingerprintValues`."""
    return FingerprintValues(
        user_agent=fingerprint.user_agent,
        cpu_cores=fingerprint.cpu_cores,
        device_memory=fingerprint.device_memory,
        timezone=fingerprint.timezone,
        locale=fingerprint.locale,
    )


class FingerprintRepository:
    """Repository pattern for Fingerprint model operations.

    Accepts session, uses flush() not commit(). Transaction management is
    handled by the caller (service or test).
    """

    def __init__(self, session: AsyncSession):
        """Initialize repository with session injection.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def create(
        self, *, values: FingerprintValues, label: str | None, created_by: int
    ) -> dict:
        """Create a new fingerprint profile.

        Args:
            values: the five (possibly partial) fingerprint fields
            label: auto-generated display label (may be None)
            created_by: Telegram user_id who created this profile (audit only)

        Returns:
            Created fingerprint data as dict

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            fingerprint = Fingerprint(
                user_agent=values.user_agent,
                cpu_cores=values.cpu_cores,
                device_memory=values.device_memory,
                timezone=values.timezone,
                locale=values.locale,
                label=label,
                created_by=created_by,
            )
            self.session.add(fingerprint)
            await self.session.flush()  # Not commit - transaction managed by caller
            logger.info(
                f"Created fingerprint {fingerprint.id} (created_by={created_by})"
            )
            return _row_to_dict(fingerprint)
        except Exception as e:
            logger.error(f"Failed to create fingerprint (created_by={created_by}): {e}")
            raise DatabaseError(f"Failed to create fingerprint: {e}") from e

    async def get_values(self, fingerprint_id: int) -> FingerprintValues | None:
        """Get the five value fields for a fingerprint.

        Args:
            fingerprint_id: surrogate fingerprint id

        Returns:
            FingerprintValues or None if not found

        Raises:
            DatabaseError: If database query fails
        """
        try:
            stmt = sa.select(Fingerprint).where(Fingerprint.id == fingerprint_id)
            result = await self.session.execute(stmt)
            fingerprint = result.scalar_one_or_none()
            return _row_to_values(fingerprint) if fingerprint else None
        except Exception as e:
            logger.error(f"Failed to get fingerprint values {fingerprint_id}: {e}")
            raise DatabaseError(f"Failed to get fingerprint values: {e}") from e

    async def get(self, fingerprint_id: int) -> dict | None:
        """Get the full fingerprint row.

        Args:
            fingerprint_id: surrogate fingerprint id

        Returns:
            Fingerprint data as dict or None if not found

        Raises:
            DatabaseError: If database query fails
        """
        try:
            stmt = sa.select(Fingerprint).where(Fingerprint.id == fingerprint_id)
            result = await self.session.execute(stmt)
            fingerprint = result.scalar_one_or_none()
            return _row_to_dict(fingerprint) if fingerprint else None
        except Exception as e:
            logger.error(f"Failed to get fingerprint {fingerprint_id}: {e}")
            raise DatabaseError(f"Failed to get fingerprint: {e}") from e

    async def get_many(self, fingerprint_ids: list[int]) -> dict[int, dict]:
        """Get full rows for several fingerprints in one query.

        Args:
            fingerprint_ids: surrogate fingerprint ids to fetch

        Returns:
            Mapping of `id -> row dict` for every id that exists; ids with no
            matching row are simply absent from the result. Empty input
            returns an empty dict without querying.

        Raises:
            DatabaseError: If database query fails
        """
        if not fingerprint_ids:
            return {}
        try:
            stmt = sa.select(Fingerprint).where(Fingerprint.id.in_(fingerprint_ids))
            result = await self.session.execute(stmt)
            return {fp.id: _row_to_dict(fp) for fp in result.scalars()}
        except Exception as e:
            logger.error(f"Failed to get fingerprints {fingerprint_ids}: {e}")
            raise DatabaseError(f"Failed to get fingerprints: {e}") from e

    async def update_values(
        self, fingerprint_id: int, values: FingerprintValues, label: str | None
    ) -> dict | None:
        """Overwrite all five value fields and the label of a fingerprint.

        Affects every session bound to this fingerprint (shared-by-reference).

        Args:
            fingerprint_id: surrogate fingerprint id
            values: the five (possibly partial) fingerprint fields, full replace
            label: new display label

        Returns:
            Updated fingerprint data as dict, or None if not found

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            stmt = (
                sa.update(Fingerprint)
                .where(Fingerprint.id == fingerprint_id)
                .values(
                    user_agent=values.user_agent,
                    cpu_cores=values.cpu_cores,
                    device_memory=values.device_memory,
                    timezone=values.timezone,
                    locale=values.locale,
                    label=label,
                )
                .returning(Fingerprint)
            )
            result = await self.session.execute(stmt)
            await self.session.flush()
            fingerprint = result.scalar_one_or_none()

            if fingerprint:
                logger.info(f"Updated fingerprint values {fingerprint_id}")
                return _row_to_dict(fingerprint)
            return None
        except Exception as e:
            logger.error(f"Failed to update fingerprint values {fingerprint_id}: {e}")
            raise DatabaseError(f"Failed to update fingerprint values: {e}") from e

    async def delete(self, fingerprint_id: int) -> bool:
        """Delete a fingerprint profile.

        Args:
            fingerprint_id: surrogate fingerprint id

        Returns:
            True if deleted, False if not found

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            stmt = sa.delete(Fingerprint).where(Fingerprint.id == fingerprint_id)
            result = await self.session.execute(stmt)
            await self.session.flush()
            # DELETE without RETURNING always yields a CursorResult (has rowcount).
            deleted = cast(CursorResult, result).rowcount > 0
            if deleted:
                logger.info(f"Deleted fingerprint {fingerprint_id}")
            return deleted
        except Exception as e:
            logger.error(f"Failed to delete fingerprint {fingerprint_id}: {e}")
            raise DatabaseError(f"Failed to delete fingerprint: {e}") from e
