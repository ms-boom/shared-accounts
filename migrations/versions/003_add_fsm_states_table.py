"""add fsm states table

Revision ID: 003
Revises: 002
Create Date: 2025-11-17

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create FSM states table for PostgreSQL-based state storage."""
    op.create_table(
        "fsm_states",
        sa.Column(
            "chat_id",
            sa.BigInteger(),
            nullable=False,
            comment="Telegram chat_id",
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            nullable=False,
            comment="Telegram user_id",
        ),
        sa.Column(
            "thread_id",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
            comment="Telegram thread_id (0 for main chat, >0 for topics)",
        ),
        sa.Column(
            "state",
            sa.Text(),
            nullable=True,
            comment="Current FSM state (None if no active state)",
        ),
        sa.Column(
            "data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
            comment="State data storage (JSON)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Last time state was updated",
        ),
        sa.PrimaryKeyConstraint("chat_id", "user_id", "thread_id"),
    )


def downgrade() -> None:
    """Drop FSM states table."""
    op.drop_table("fsm_states")
