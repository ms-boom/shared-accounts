"""SQLAlchemy database models."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


class Group(Base):
    """
    Telegram group model.

    Stores information about groups where the bot is present.
    """

    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        comment="Telegram chat_id",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Group title",
    )
    username: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Group username (@group_name)",
    )
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Chat type: 'group' or 'supergroup'",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="When group was first registered",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Last time group info was updated",
    )

    def __repr__(self) -> str:
        return f"<Group(id={self.id}, title='{self.title}', type='{self.type}')>"


class User(Base):
    """
    Telegram user model.

    Stores information about users who interact with the bot.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        comment="Telegram user_id",
    )
    username: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="User username (@username)",
    )
    first_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="User first name",
    )
    last_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="User last name",
    )
    language_code: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="User language code (from Telegram)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="When user first interacted with bot",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Last time user info was updated",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', first_name='{self.first_name}')>"


class ChatSession(Base):
    """
    Claude browser session for a chat or topic.

    Stores Playwright session information for each (chat_id, thread_id) pair.
    Allows automated interaction with Claude.ai.

    thread_id = 0 means main chat (not a topic).
    thread_id > 0 identifies a specific topic/thread in the chat.
    """

    __tablename__ = "chat_sessions"

    chat_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        comment="Telegram chat_id",
    )
    thread_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        server_default="0",
        comment="Telegram thread_id (0 for main chat, >0 for topics)",
    )
    email: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Email address associated with this Claude session",
    )
    session_path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="File system path to Playwright session data",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="When session was initialized",
    )
    last_used: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="Last time this session was used for /get_code",
    )

    def __repr__(self) -> str:
        thread_str = f", thread_id={self.thread_id}" if self.thread_id else ""
        return (
            f"<ChatSession(chat_id={self.chat_id}{thread_str}, email='{self.email}')>"
        )


class Task(Base):
    """
    Background task queue entry.

    Tasks are processed asynchronously by worker service.
    Uses PostgreSQL row-level locking for safe concurrent processing.
    """

    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Unique task ID",
    )
    chat_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
        comment="Telegram chat_id for this task",
    )
    thread_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default="0",
        comment="Telegram thread_id (0 for main chat, >0 for topics)",
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Telegram user_id who initiated task",
    )
    task_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Task type: 'init_session' or 'get_code'",
    )
    payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Task-specific payload (email, url, etc.)",
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="pending",
        comment="Task status: pending, processing, done, failed",
    )
    result: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Task result or error message",
    )
    version: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default="1",
        comment="Version for optimistic locking",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="When task was created",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Last time task was updated",
    )

    __table_args__ = (
        Index(
            "idx_tasks_pending_status",
            "status",
            postgresql_where=lambda: Task.status == "pending",
        ),
    )

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, type='{self.task_type}', status='{self.status}')>"


class FSMState(Base):
    """
    Finite State Machine state storage for aiogram.

    Stores user/chat states and associated data for FSM workflows.
    Provides persistent storage for conversation states across bot restarts.
    """

    __tablename__ = "fsm_states"

    chat_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        comment="Telegram chat_id",
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        comment="Telegram user_id",
    )
    thread_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        server_default="0",
        comment="Telegram thread_id (0 for main chat, >0 for topics)",
    )
    state: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Current FSM state (None if no active state)",
    )
    data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="State data storage (JSON)",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Last time state was updated",
    )

    def __repr__(self) -> str:
        return f"<FSMState(chat_id={self.chat_id}, user_id={self.user_id}, state='{self.state}')>"
