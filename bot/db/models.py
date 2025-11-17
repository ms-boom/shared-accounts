"""SQLAlchemy database models."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
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
