"""fingerprints

Revision ID: 002
Revises: 001
Create Date: 2026-07-25

Adds two new tables for per-session browser fingerprint profiles:
`fingerprints` (the stored values, audit-only `created_by`) and
`session_fingerprints` (the (chat_id, thread_id) -> fingerprint binding).

No data backfill: existing sessions have no binding row, so resolution falls
back to the default profile purely behaviorally.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create fingerprints and session_fingerprints tables."""
    op.create_table(
        "fingerprints",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
            autoincrement=True,
            comment="Surrogate autoincrement ID (not a Telegram id)",
        ),
        sa.Column(
            "user_agent",
            sa.Text(),
            nullable=True,
            comment="Browser User-Agent string override",
        ),
        sa.Column(
            "cpu_cores",
            sa.Integer(),
            nullable=True,
            comment="navigator.hardwareConcurrency override",
        ),
        sa.Column(
            "device_memory",
            sa.Integer(),
            nullable=True,
            comment="navigator.deviceMemory override, in GB",
        ),
        sa.Column(
            "timezone",
            sa.Text(),
            nullable=True,
            comment="IANA timezone override, e.g. 'America/New_York'",
        ),
        sa.Column(
            "locale",
            sa.Text(),
            nullable=True,
            comment="Locale override, e.g. 'en-US'",
        ),
        sa.Column(
            "label",
            sa.Text(),
            nullable=True,
            comment="Auto-generated display label",
        ),
        sa.Column(
            "created_by",
            sa.BigInteger(),
            nullable=False,
            comment="Telegram user_id who created this profile — audit only, no authority",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
            comment="When this profile was created",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
            comment="Last time this profile was updated",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "session_fingerprints",
        sa.Column(
            "chat_id",
            sa.BigInteger(),
            nullable=False,
            comment="Telegram chat_id",
        ),
        sa.Column(
            "thread_id",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
            comment="Telegram thread_id (0 for main chat, >0 for topics)",
        ),
        sa.Column(
            "fingerprint_id",
            sa.Integer(),
            nullable=False,
            comment="Bound Fingerprint profile",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
            comment="When this binding was created",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
            comment="Last time this binding was updated",
        ),
        sa.PrimaryKeyConstraint("chat_id", "thread_id"),
        sa.ForeignKeyConstraint(["fingerprint_id"], ["fingerprints.id"]),
    )
    op.create_index(
        "ix_session_fingerprints_fingerprint_id",
        "session_fingerprints",
        ["fingerprint_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop session_fingerprints and fingerprints tables in reverse dependency order."""
    op.drop_index(
        "ix_session_fingerprints_fingerprint_id", table_name="session_fingerprints"
    )
    op.drop_table("session_fingerprints")
    op.drop_table("fingerprints")
