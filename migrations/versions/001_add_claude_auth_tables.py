"""add claude auth tables

Revision ID: 001
Revises:
Create Date: 2025-11-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create tables for Claude Authorization Bot."""
    # Create groups table
    op.create_table(
        "groups",
        sa.Column("id", sa.BigInteger(), nullable=False, comment="Telegram chat_id"),
        sa.Column("title", sa.String(length=255), nullable=False, comment="Group title"),
        sa.Column(
            "username",
            sa.String(length=255),
            nullable=True,
            comment="Group username (@group_name)",
        ),
        sa.Column(
            "type",
            sa.String(length=50),
            nullable=False,
            comment="Chat type: 'group' or 'supergroup'",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When group was first registered",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Last time group info was updated",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_groups_username"), "groups", ["username"], unique=False)

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), nullable=False, comment="Telegram user_id"),
        sa.Column(
            "username",
            sa.String(length=255),
            nullable=True,
            comment="User username (@username)",
        ),
        sa.Column(
            "first_name", sa.String(length=255), nullable=False, comment="User first name"
        ),
        sa.Column(
            "last_name", sa.String(length=255), nullable=True, comment="User last name"
        ),
        sa.Column(
            "language_code",
            sa.String(length=10),
            nullable=True,
            comment="User language code (from Telegram)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When user first interacted with bot",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Last time user info was updated",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=False)

    # Create chat_sessions table
    op.create_table(
        "chat_sessions",
        sa.Column(
            "chat_id",
            sa.BigInteger(),
            nullable=False,
            comment="Telegram chat_id (unique per session)",
        ),
        sa.Column(
            "email",
            sa.Text(),
            nullable=False,
            comment="Email address associated with this Claude session",
        ),
        sa.Column(
            "session_path",
            sa.Text(),
            nullable=False,
            comment="File system path to Playwright session data",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When session was initialized",
        ),
        sa.Column(
            "last_used",
            sa.DateTime(),
            nullable=True,
            comment="Last time this session was used for /get_code",
        ),
        sa.PrimaryKeyConstraint("chat_id"),
    )

    # Create tasks table
    op.create_table(
        "tasks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Unique task ID",
        ),
        sa.Column(
            "chat_id",
            sa.BigInteger(),
            nullable=False,
            comment="Telegram chat_id for this task",
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            nullable=False,
            comment="Telegram user_id who initiated task",
        ),
        sa.Column(
            "task_type",
            sa.Text(),
            nullable=False,
            comment="Task type: 'init_session' or 'get_code'",
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Task-specific payload (email, url, etc.)",
        ),
        sa.Column(
            "status",
            sa.Text(),
            server_default="pending",
            nullable=False,
            comment="Task status: pending, processing, done, failed",
        ),
        sa.Column(
            "result",
            sa.Text(),
            nullable=True,
            comment="Task result or error message",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When task was created",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Last time task was updated",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tasks_chat_id"), "tasks", ["chat_id"], unique=False)
    op.create_index(
        "idx_tasks_pending_status",
        "tasks",
        ["status"],
        unique=False,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    """Drop tables for Claude Authorization Bot."""
    op.drop_index("idx_tasks_pending_status", table_name="tasks")
    op.drop_index(op.f("ix_tasks_chat_id"), table_name="tasks")
    op.drop_table("tasks")
    op.drop_table("chat_sessions")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_table("users")
    op.drop_index(op.f("ix_groups_username"), table_name="groups")
    op.drop_table("groups")
