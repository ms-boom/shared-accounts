"""Tests verifying handlers route writes through writer_queue.

These tests ensure that claude_auth handlers use database.writer_queue.execute()
for all write operations instead of direct session.begin().
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import Chat, Message, User
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.handlers.claude_auth import (
    get_code_handler,
    handle_claude_url,
    init_session_handler,
)
from core.config import Settings
from core.db.database import Database


def _make_writer_queue_mock(session_maker: async_sessionmaker[AsyncSession]) -> MagicMock:
    """Create a writer_queue mock that executes fn through the test session."""

    async def _execute(fn):  # noqa: ANN001
        async with session_maker() as session, session.begin():
            return await fn(session)

    mock = MagicMock()
    mock.execute = AsyncMock(side_effect=_execute)
    return mock


def _make_mock_database(
    session_maker: async_sessionmaker[AsyncSession],
) -> MagicMock:
    """Create a mock Database with real session_maker and writer_queue mock."""
    mock_db = MagicMock(spec=Database)
    mock_db.session_maker = session_maker
    mock_db.writer_queue = _make_writer_queue_mock(session_maker)
    return mock_db


def _make_message(
    *,
    chat_id: int = -100123456789,
    user_id: int = 123456789,
    text: str = "",
    chat_type: str = "private",
    thread_id: int | None = None,
) -> MagicMock:
    """Create a mock Telegram Message."""
    message = MagicMock(spec=Message)
    message.chat = MagicMock(spec=Chat)
    message.chat.id = chat_id
    message.chat.type = chat_type
    message.from_user = MagicMock(spec=User)
    message.from_user.id = user_id
    message.text = text
    message.message_thread_id = thread_id
    message.reply = AsyncMock()
    message.bot = MagicMock()
    message.bot.get_chat_member = AsyncMock()
    return message


@pytest.mark.unit
class TestInitSessionHandlerWriterQueue:
    """Verify init_session_handler routes task creation through writer_queue."""

    async def test_creates_task_through_writer_queue(
        self,
        db_sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        """init_session_handler must call writer_queue.execute() to create a task."""
        mock_db = _make_mock_database(db_sessionmaker)
        message = _make_message(text="/init_session test@example.com")

        settings = MagicMock(spec=Settings)

        await init_session_handler(message, mock_db, settings)

        mock_db.writer_queue.execute.assert_called_once()
        message.reply.assert_called()

    async def test_task_created_in_db_through_writer_queue(
        self,
        db_sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        """Task must actually be persisted when going through writer_queue."""
        mock_db = _make_mock_database(db_sessionmaker)
        message = _make_message(text="/init_session test@example.com")

        settings = MagicMock(spec=Settings)

        await init_session_handler(message, mock_db, settings)

        # Verify task was persisted by querying the DB
        from core.db.repositories.task_repository import TaskRepository

        async with db_sessionmaker() as session:
            repo = TaskRepository(session)
            tasks = await repo.get_by_chat_id(message.chat.id, thread_id=0)
            assert len(tasks) == 1
            assert tasks[0]["task_type"] == "init_session"
            assert tasks[0]["payload"]["email"] == "test@example.com"


@pytest.mark.unit
class TestGetCodeHandlerWriterQueue:
    """Verify get_code_handler routes task creation through writer_queue."""

    async def test_creates_task_through_writer_queue(
        self,
        db_sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        """get_code_handler must call writer_queue.execute() to create a task."""
        mock_db = _make_mock_database(db_sessionmaker)

        # First, create a chat session so get_code_handler finds it
        from core.db.repositories.chat_session_repository import ChatSessionRepository

        async with db_sessionmaker() as session, session.begin():
            repo = ChatSessionRepository(session)
            await repo.create(
                chat_id=-100123456789,
                email="test@example.com",
                session_path="/data/sessions/test",
            )

        message = _make_message(
            text="/get_code https://claude.ai/auth/authorize?test=1"
        )

        await get_code_handler(message, mock_db)

        mock_db.writer_queue.execute.assert_called_once()
        message.reply.assert_called()

    async def test_no_writer_queue_call_when_no_session(
        self,
        db_sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        """get_code_handler should not call writer_queue if no session exists (read-only)."""
        mock_db = _make_mock_database(db_sessionmaker)

        message = _make_message(
            text="/get_code https://claude.ai/auth/authorize?test=1"
        )

        await get_code_handler(message, mock_db)

        mock_db.writer_queue.execute.assert_not_called()


@pytest.mark.unit
class TestHandleClaudeUrlWriterQueue:
    """Verify handle_claude_url routes task creation through writer_queue."""

    async def test_creates_task_through_writer_queue(
        self,
        db_sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        """handle_claude_url must call writer_queue.execute() to create a task."""
        mock_db = _make_mock_database(db_sessionmaker)

        # Create a pending init_session task so handle_claude_url processes the URL
        from core.db.repositories.task_repository import TaskRepository

        async with db_sessionmaker() as session, session.begin():
            repo = TaskRepository(session)
            await repo.create(
                chat_id=-100123456789,
                user_id=123456789,
                task_type="init_session",
                payload={"email": "test@example.com"},
                thread_id=0,
            )

        message = _make_message(
            text="https://claude.ai/login?token=test-login-token-123"
        )

        await handle_claude_url(message, mock_db)

        mock_db.writer_queue.execute.assert_called_once()
        message.reply.assert_called()
