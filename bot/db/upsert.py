"""Dialect-aware upsert helper for SQLAlchemy."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.dml import Insert

from bot.db.models import Base


def build_upsert(
    model: type[Base],
    values: dict[str, Any],
    conflict_columns: list[str],
    update_columns: dict[str, Any],
    session: AsyncSession,
) -> Insert:
    """Build dialect-aware INSERT ... ON CONFLICT ... DO UPDATE statement.

    Detects the SQL dialect from the session's bound engine and selects the
    appropriate dialect-specific insert implementation.

    Args:
        model: SQLAlchemy declarative model class
        values: Column values for the INSERT clause
        conflict_columns: Column names that define the unique constraint
        update_columns: Column name to value mapping for the UPDATE SET clause
        session: Active AsyncSession used to detect the SQL dialect

    Returns:
        Compiled Insert statement ready for session.execute()

    Raises:
        RuntimeError: If session has no bound engine (dialect cannot be detected)
    """
    if session.bind is None:
        raise RuntimeError(
            "Cannot detect SQL dialect: session has no bound engine. "
            "Ensure the session is created from a configured session factory."
        )

    dialect_name = session.bind.dialect.name

    if dialect_name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as _insert
    else:
        from sqlalchemy.dialects.sqlite import insert as _insert  # type: ignore[assignment]

    return _insert(model).values(**values).on_conflict_do_update(
        index_elements=conflict_columns,
        set_=update_columns,
    )
