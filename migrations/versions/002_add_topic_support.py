"""add topic support

Revision ID: 002
Revises: 001
Create Date: 2025-11-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add thread_id support for Telegram topics."""
    # Add thread_id to chat_sessions table
    op.add_column(
        "chat_sessions",
        sa.Column(
            "thread_id",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
            comment="Telegram thread_id (0 for main chat, >0 for topics)",
        ),
    )

    # Drop old primary key constraint
    op.drop_constraint("chat_sessions_pkey", "chat_sessions", type_="primary")

    # Create new composite primary key
    op.create_primary_key(
        "chat_sessions_pkey",
        "chat_sessions",
        ["chat_id", "thread_id"],
    )

    # Add thread_id to tasks table
    op.add_column(
        "tasks",
        sa.Column(
            "thread_id",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
            comment="Telegram thread_id (0 for main chat, >0 for topics)",
        ),
    )


def downgrade() -> None:
    """Remove thread_id support."""
    # Remove thread_id from tasks table
    op.drop_column("tasks", "thread_id")

    # Drop composite primary key from chat_sessions
    op.drop_constraint("chat_sessions_pkey", "chat_sessions", type_="primary")

    # Create old single-column primary key
    op.create_primary_key("chat_sessions_pkey", "chat_sessions", ["chat_id"])

    # Remove thread_id from chat_sessions
    op.drop_column("chat_sessions", "thread_id")
