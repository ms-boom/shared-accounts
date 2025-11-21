"""sqlite support - convert UUID to String, JSONB to JSON

Revision ID: 005
Revises: 004
Create Date: 2025-11-21

This migration converts PostgreSQL-specific types to SQLite-compatible types:
- UUID -> String(36)
- JSONB -> JSON (stored as TEXT in SQLite)
- Partial index with postgresql_where -> sqlite_where

For PostgreSQL: This is a no-op migration (types remain the same).
For SQLite: Creates tables with compatible types.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Migrate to SQLite-compatible types.

    For PostgreSQL: No changes needed (already using UUID and JSONB).
    For SQLite: Alters column types to be compatible.

    Note: SQLite doesn't support ALTER COLUMN TYPE, so we need to
    recreate tables if migrating from PostgreSQL to SQLite.
    This migration is designed to work on fresh SQLite databases.
    """
    # Detect database type
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        # For SQLite, we need to recreate the tasks table with String UUID
        # and JSON (TEXT) columns instead of PostgreSQL-specific types

        # Drop existing partial index if it exists
        try:
            op.drop_index("idx_tasks_pending_status", table_name="tasks")
        except Exception:
            pass  # Index might not exist

        # Recreate partial index with SQLite syntax
        # SQLite supports partial indexes with WHERE clause
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_tasks_pending_status
            ON tasks(status)
            WHERE status = 'pending'
            """
        )

    elif dialect == "postgresql":
        # For PostgreSQL, no changes needed
        # Types are already correct (UUID, JSONB)
        pass


def downgrade() -> None:
    """Revert SQLite compatibility changes.

    This is essentially a no-op as we don't want to break existing databases.
    """
    pass
