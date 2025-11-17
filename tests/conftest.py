"""Shared test fixtures and configuration."""

import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from aiogram import Bot
from aiogram.types import Chat, ChatMember, User
from databases import Database

from bot.core.config import Settings
from bot.core.exceptions import DatabaseError


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
    Create test database with schema.

    Args:
        test_settings: Test settings fixture

    Yields:
        Connected database instance

    Note:
        Automatically creates schema and cleans up after test
    """
    database = Database(test_settings.DATABASE_URL)

    await database.connect()

    # Create schema
    await _create_test_schema(database)

    yield database

    await database.disconnect()


async def _create_test_schema(database: Database) -> None:
    """
    Create test database schema.

    Args:
        database: Database connection

    Raises:
        DatabaseError: If schema creation fails
    """
    schema_queries = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT NOT NULL,
            last_name TEXT,
            language_code TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            type TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS chat_sessions (
            chat_id INTEGER PRIMARY KEY,
            email TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            task_type TEXT NOT NULL,
            payload TEXT NOT NULL,
            status TEXT NOT NULL,
            result TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
    ]

    try:
        for query in schema_queries:
            await database.execute(query)
    except Exception as e:
        raise DatabaseError(f"Failed to create test schema: {e}") from e


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
def admin_chat_member(telegram_user: User, telegram_chat: Chat) -> ChatMember:
    """
    Create admin ChatMember.

    Args:
        telegram_user: Telegram user fixture
        telegram_chat: Telegram chat fixture

    Returns:
        ChatMember with admin status
    """
    return ChatMember(
        user=telegram_user,
        status="administrator",
    )


@pytest.fixture
def regular_chat_member(telegram_user: User, telegram_chat: Chat) -> ChatMember:
    """
    Create regular ChatMember.

    Args:
        telegram_user: Telegram user fixture
        telegram_chat: Telegram chat fixture

    Returns:
        ChatMember with member status
    """
    return ChatMember(
        user=telegram_user,
        status="member",
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
