"""Shared test fixtures and configuration."""

import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.types import Chat, ChatMemberAdministrator, ChatMemberMember, User
from databases import Database
from sqlalchemy import JSON
from sqlalchemy.ext.asyncio import create_async_engine

from bot.core.config import Settings
from bot.db.models import Base


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """
    Create temporary directory for tests.

    Args:
        tmp_path: pytest's temporary directory fixture

    Returns:
        Path to temporary directory
    """
    return tmp_path


@pytest.fixture
def test_settings(temp_dir: Path) -> Settings:
    """
    Create test settings with safe defaults.

    Args:
        temp_dir: Temporary directory for test data

    Returns:
        Settings instance configured for testing
    """
    os.environ["TELEGRAM_TOKEN"] = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"

    return Settings(
        TELEGRAM_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        DATABASE_URL=f"sqlite+aiosqlite:///{temp_dir}/test.db",
        LOG_LEVEL="DEBUG",
        DEBUG=True,
        DATA_DIR=temp_dir / "data",
        SESSION_DIR=temp_dir / "sessions",
        LOG_DIR=temp_dir / "logs",
        ERROR_DIR=temp_dir / "errors",
        PERMISSION_CACHE_TTL=1,  # Short TTL for testing
    )


@pytest.fixture
async def test_database(test_settings: Settings) -> AsyncIterator[Database]:
    """
    Create test database with schema using SQLAlchemy models.

    Uses SQLAlchemy Base.metadata.create_all() to create schema from models.
    This ensures test schema matches production models defined in bot/db/models.py.

    Args:
        test_settings: Test settings fixture

    Yields:
        Connected database instance

    Note:
        - Automatically creates schema from SQLAlchemy models
        - Cleans up after test
        - For SQLite: PostgreSQL-specific types (JSONB → JSON) are automatically adapted
        - For full integration tests with migrations, use PostgreSQL database
    """
    # Create async engine for schema creation
    engine = create_async_engine(test_settings.DATABASE_URL, echo=False)

    # For SQLite, replace JSONB with JSON (SQLite-compatible)
    # NOTE: This is a test-only workaround. Production uses PostgreSQL exclusively.
    if "sqlite" in test_settings.DATABASE_URL:
        original_types: dict[str, Any] = {}

        # Adapt tasks.payload column
        tasks_table = Base.metadata.tables.get("tasks")
        if tasks_table is not None:
            payload_column = tasks_table.c.payload
            original_types["tasks.payload"] = payload_column.type
            payload_column.type = JSON()

        # Adapt fsm_states.data column
        fsm_states_table = Base.metadata.tables.get("fsm_states")
        if fsm_states_table is not None:
            data_column = fsm_states_table.c.data
            original_types["fsm_states.data"] = data_column.type
            data_column.type = JSON()

        try:
            # Create all tables from models
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        finally:
            # Restore original types
            if tasks_table is not None and "tasks.payload" in original_types:
                tasks_table.c.payload.type = original_types["tasks.payload"]
            if fsm_states_table is not None and "fsm_states.data" in original_types:
                fsm_states_table.c.data.type = original_types["fsm_states.data"]
    else:
        # For PostgreSQL, use original models
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # Create databases connection for tests
    database = Database(test_settings.DATABASE_URL)
    await database.connect()

    yield database

    # Cleanup
    await database.disconnect()

    # Drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
def mock_bot() -> MagicMock:
    """
    Create mock Bot instance.

    Returns:
        Mocked Bot with common methods
    """
    bot = MagicMock(spec=Bot)
    bot.get_chat_member = AsyncMock()
    bot.send_message = AsyncMock()
    return bot


@pytest.fixture
def telegram_user() -> User:
    """
    Create mock Telegram user.

    Returns:
        User instance for testing
    """
    return User(
        id=123456789,
        is_bot=False,
        first_name="Test",
        last_name="User",
        username="testuser",
        language_code="en",
    )


@pytest.fixture
def telegram_chat() -> Chat:
    """
    Create mock Telegram chat.

    Returns:
        Chat instance for testing
    """
    return Chat(
        id=-100123456789,
        type="supergroup",
        title="Test Group",
    )


@pytest.fixture
def admin_chat_member(telegram_user: User) -> ChatMemberAdministrator:
    """
    Create admin ChatMemberAdministrator.

    Args:
        telegram_user: Telegram user fixture

    Returns:
        ChatMemberAdministrator with admin permissions
    """
    return ChatMemberAdministrator(
        user=telegram_user,
        status=ChatMemberStatus.ADMINISTRATOR,
        can_be_edited=False,
        is_anonymous=False,
        can_manage_chat=True,
        can_delete_messages=True,
        can_manage_video_chats=True,
        can_restrict_members=True,
        can_promote_members=False,
        can_change_info=True,
        can_invite_users=True,
        can_post_stories=False,
        can_edit_stories=False,
        can_delete_stories=False,
        can_post_messages=None,
        can_edit_messages=None,
        can_pin_messages=True,
        can_manage_topics=True,
        can_manage_direct_messages=False,
    )


@pytest.fixture
def regular_chat_member(telegram_user: User) -> ChatMemberMember:
    """
    Create regular ChatMemberMember.

    Args:
        telegram_user: Telegram user fixture

    Returns:
        ChatMemberMember with member status
    """
    return ChatMemberMember(
        user=telegram_user,
        status=ChatMemberStatus.MEMBER,
    )


@pytest.fixture
def task_id() -> str:
    """
    Generate unique task ID.

    Returns:
        UUID string for task testing
    """
    return str(uuid4())


@pytest.fixture
def sample_task_payload() -> dict[str, Any]:
    """
    Create sample task payload.

    Returns:
        Task payload for testing
    """
    return {
        "email": "test@example.com",
        "action": "init_session",
    }
