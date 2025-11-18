"""add version to tasks

Revision ID: 004
Revises: 003
Create Date: 2025-11-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add version column to tasks table for optimistic locking."""
    op.add_column(
        "tasks",
        sa.Column(
            "version",
            sa.BigInteger(),
            nullable=False,
            server_default="1",
            comment="Version for optimistic locking",
        ),
    )


def downgrade() -> None:
    """Remove version column from tasks table."""
    op.drop_column("tasks", "version")
