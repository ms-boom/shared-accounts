"""Unit tests for handle_claude_url handler.

Covers the URL detection logic and task status matching,
including the 'done' status that was recently added alongside
'pending' and 'processing'.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Chat, Message, User
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.handlers.claude_auth import handle_claude_url
from core.db.database import Database
from core.db.repositories.task_repository import TaskRepository


def _make_mock_database(
    session_maker: async_sessionmaker[AsyncSession],
) -> MagicMock:
    """Create a mock Database with real session_maker and db.write/read mocks."""

    async def _write(fn):  # noqa: ANN001
        async with session_maker() as session, session.begin():
            return await fn(session)

    mock_db = MagicMock(spec=Database)
    mock_db.session_maker = session_maker
    mock_db.write = AsyncMock(side_effect=_write)
    mock_db.read = session_maker
    return mock_db


def _make_message(
    *,
    chat_id: int = -100123456789,
    user_id: int = 123456789,
    text: str = "",
    thread_id: int | None = None,
    from_user: User | MagicMock | None = "default",
) -> MagicMock:
    """Create a mock Telegram Message."""
    message = MagicMock(spec=Message)
    message.chat = MagicMock(spec=Chat)
    message.chat.id = chat_id
    message.chat.type = "private"
    message.text = text
    message.message_thread_id = thread_id
    message.reply = AsyncMock()

    if from_user == "default":
        message.from_user = MagicMock(spec=User)
        message.from_user.id = user_id
    else:
        message.from_user = from_user

    return message


async def _create_init_task(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    chat_id: int = -100123456789,
    user_id: int = 123456789,
    thread_id: int = 0,
    status: str = "pending",
) -> dict:
    """Helper to create an init_session task with a specific status."""
    async with session_maker() as session, session.begin():
        repo = TaskRepository(session)
        task = await repo.create(
            chat_id=chat_id,
            user_id=user_id,
            task_type="init_session",
            payload={"email": "test@example.com"},
            thread_id=thread_id,
        )
        # Update status if not pending (default after create)
        if status != "pending":
            await repo.update_status(
                task["id"], status, expected_version=task["version"]
            )
        return task


@pytest.mark.unit
class TestHandleClaudeUrlStatusMatching:
    """Tests for handle_claude_url matching init_session tasks by status.

    The handler looks for init_session tasks with status in
    ['done', 'pending', 'processing'] and creates a process_login_link task.
    """

    async def test__handle_claude_url__done_status__creates_login_task(
        self,
        db_sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        """Task with 'done' status should be matched by handle_claude_url."""
        await _create_init_task(db_sessionmaker, status="done")
        mock_db = _make_mock_database(db_sessionmaker)
        message = _make_message(
            text="https://claude.ai/login?token=test-token-123"
        )

        await handle_claude_url(message, mock_db)

        mock_db.write.assert_called_once()
        reply_text = message.reply.call_args[0][0]
        assert "Processing login link" in reply_text

    async def test__handle_claude_url__pending_status__creates_login_task(
        self,
        db_sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        """Task with 'pending' status should be matched."""
        await _create_init_task(db_sessionmaker, status="pending")
        mock_db = _make_mock_database(db_sessionmaker)
        message = _make_message(
            text="https://claude.ai/login?token=test-token-pending"
        )

        await handle_claude_url(message, mock_db)

        mock_db.write.assert_called_once()

    async def test__handle_claude_url__processing_status__creates_login_task(
        self,
        db_sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        """Task with 'processing' status should be matched."""
        await _create_init_task(db_sessionmaker, status="processing")
        mock_db = _make_mock_database(db_sessionmaker)
        message = _make_message(
            text="https://claude.ai/login?token=test-token-processing"
        )

        await handle_claude_url(message, mock_db)

        mock_db.write.assert_called_once()

    async def test__handle_claude_url__failed_status__shows_info_message(
        self,
        db_sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        """Task with 'failed' status should NOT be matched."""
        await _create_init_task(db_sessionmaker, status="failed")
        mock_db = _make_mock_database(db_sessionmaker)
        message = _make_message(
            text="https://claude.ai/login?token=test-token-failed"
        )

        await handle_claude_url(message, mock_db)

        mock_db.write.assert_not_called()
        reply_text = message.reply.call_args[0][0]
        assert "init_session" in reply_text.lower() or "/init_session" in reply_text


@pytest.mark.unit
class TestHandleClaudeUrlFiltering:
    """Tests for handle_claude_url message filtering logic."""

    async def test__handle_claude_url__no_text__returns_silently(
        self,
        db_sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        mock_db = _make_mock_database(db_sessionmaker)
        message = _make_message(text="")
        message.text = None

        await handle_claude_url(message, mock_db)

        message.reply.assert_not_called()
        mock_db.write.assert_not_called()

    async def test__handle_claude_url__non_claude_url__returns_silently(
        self,
        db_sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        mock_db = _make_mock_database(db_sessionmaker)
        message = _make_message(text="https://google.com/some-page")

        await handle_claude_url(message, mock_db)

        message.reply.assert_not_called()
        mock_db.write.assert_not_called()

    async def test__handle_claude_url__plain_text__returns_silently(
        self,
        db_sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        mock_db = _make_mock_database(db_sessionmaker)
        message = _make_message(text="Hello, this is a regular message")

        await handle_claude_url(message, mock_db)

        message.reply.assert_not_called()
        mock_db.write.assert_not_called()

    async def test__handle_claude_url__magic_link_url__creates_task(
        self,
        db_sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        """magic-link URLs should be recognized and processed."""
        await _create_init_task(db_sessionmaker, status="done")
        mock_db = _make_mock_database(db_sessionmaker)
        message = _make_message(
            text="https://claude.ai/magic-link#some-token"
        )

        await handle_claude_url(message, mock_db)

        mock_db.write.assert_called_once()

    async def test__handle_claude_url__no_init_task__shows_info(
        self,
        db_sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        """When no init_session task exists, show informational message."""
        mock_db = _make_mock_database(db_sessionmaker)
        message = _make_message(
            text="https://claude.ai/login?token=orphan-token"
        )

        await handle_claude_url(message, mock_db)

        mock_db.write.assert_not_called()
        message.reply.assert_called_once()
        reply_text = message.reply.call_args[0][0]
        assert "/init_session" in reply_text

    async def test__handle_claude_url__no_from_user__returns_error(
        self,
        db_sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        """When from_user is None, handler should reply with error."""
        await _create_init_task(db_sessionmaker, status="done")
        mock_db = _make_mock_database(db_sessionmaker)
        message = _make_message(
            text="https://claude.ai/login?token=test-token",
            from_user=None,
        )

        await handle_claude_url(message, mock_db)

        mock_db.write.assert_not_called()
        reply_text = message.reply.call_args[0][0]
        assert "Unable to identify user" in reply_text


@pytest.mark.unit
class TestHandleClaudeUrlThreadIsolation:
    """Tests for handle_claude_url topic/thread isolation."""

    async def test__handle_claude_url__different_thread__no_match(
        self,
        db_sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        """Task in thread 0 should not match message in thread 555."""
        await _create_init_task(db_sessionmaker, thread_id=0, status="done")
        mock_db = _make_mock_database(db_sessionmaker)
        message = _make_message(
            text="https://claude.ai/login?token=thread-test",
            thread_id=555,
        )

        await handle_claude_url(message, mock_db)

        mock_db.write.assert_not_called()
        message.reply.assert_called_once()
        reply_text = message.reply.call_args[0][0]
        assert "/init_session" in reply_text

    async def test__handle_claude_url__same_thread__matches(
        self,
        db_sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        """Task in thread 555 should match message in thread 555."""
        await _create_init_task(
            db_sessionmaker, thread_id=555, status="done"
        )
        mock_db = _make_mock_database(db_sessionmaker)
        message = _make_message(
            text="https://claude.ai/login?token=thread-match",
            thread_id=555,
        )

        await handle_claude_url(message, mock_db)

        mock_db.write.assert_called_once()
