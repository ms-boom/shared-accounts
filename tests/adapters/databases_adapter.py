"""Adapter to use SQLAlchemy AsyncSession with databases.Database interface.

This adapter allows using repositories that expect databases.Database
while leveraging SQLAlchemy AsyncSession for better transaction isolation.
"""

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class DatabasesAdapter:
    """Adapter that wraps AsyncSession to provide databases.Database interface.

    This allows using existing repositories without modification while
    benefiting from SQLAlchemy's transaction management and test isolation.
    """

    def __init__(self, session: AsyncSession):
        """Initialize adapter with AsyncSession.

        Args:
            session: SQLAlchemy AsyncSession to wrap
        """
        self.session = session

    async def fetch_one(self, query: str, values: dict[str, Any] | None = None):
        """Execute query and return single row.

        Args:
            query: SQL query string
            values: Query parameters as dict

        Returns:
            Row mapping or None if no results

        Raises:
            DatabaseError: If query execution fails
        """
        result = await self.session.execute(text(query), values or {})
        row = result.mappings().first()
        return row

    async def fetch_all(
        self, query: str, values: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute query and return all rows.

        Args:
            query: SQL query string
            values: Query parameters as dict

        Returns:
            List of row mappings

        Raises:
            DatabaseError: If query execution fails
        """
        result = await self.session.execute(text(query), values or {})
        rows = result.mappings().all()
        return [dict(row) for row in rows]

    async def execute(self, query: str, values: dict[str, Any] | None = None) -> None:
        """Execute query without returning results.

        Args:
            query: SQL query string
            values: Query parameters as dict

        Raises:
            DatabaseError: If query execution fails
        """
        await self.session.execute(text(query), values or {})

    async def execute_many(self, query: str, values: list[dict[str, Any]]) -> None:
        """Execute query multiple times with different values.

        Args:
            query: SQL query string
            values: List of parameter dicts

        Raises:
            DatabaseError: If query execution fails
        """
        for value_dict in values:
            await self.session.execute(text(query), value_dict)
