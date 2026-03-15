"""Tests for handle_claude_url — task status matching logic.

The handler looks for init_session tasks with status in
['done', 'pending', 'processing'] and creates a process_login_link task.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.handlers.claude_auth import handle_claude_url
from core.db.repositories.task_repository import TaskRepository
from tests.unit.conftest import make_mock_database, make_mock_message


async def _create_init_task(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    chat_id: int = -100123456789,
    user_id: int = 123456789,
    thread_id: int = 0,
    status: str = "pending",
) -> dict:
    async with session_maker() as session, session.begin():
        repo = TaskRepository(session)
        task = await repo.create(
            chat_id=chat_id,
            user_id=user_id,
            task_type="init_session",
            payload={"email": "test@example.com"},
            thread_id=thread_id,
        )
        if status != "pending":
            await repo.update_status(
                task["id"], status, expected_version=task["version"]
            )
        return task


@pytest.mark.unit
async def test__handle_claude_url__done_status__creates_login_task(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    await _create_init_task(db_sessionmaker, status="done")
    mock_db = make_mock_database(db_sessionmaker)
    message = make_mock_message(text="https://claude.ai/login?token=test-token-123")

    await handle_claude_url(message, mock_db)

    mock_db.write.assert_called_once()
    reply_text = message.reply.call_args[0][0]
    assert "Processing login link" in reply_text


@pytest.mark.unit
async def test__handle_claude_url__pending_status__creates_login_task(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    await _create_init_task(db_sessionmaker, status="pending")
    mock_db = make_mock_database(db_sessionmaker)
    message = make_mock_message(text="https://claude.ai/login?token=test-token-pending")

    await handle_claude_url(message, mock_db)

    mock_db.write.assert_called_once()


@pytest.mark.unit
async def test__handle_claude_url__processing_status__creates_login_task(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    await _create_init_task(db_sessionmaker, status="processing")
    mock_db = make_mock_database(db_sessionmaker)
    message = make_mock_message(
        text="https://claude.ai/login?token=test-token-processing"
    )

    await handle_claude_url(message, mock_db)

    mock_db.write.assert_called_once()


@pytest.mark.unit
async def test__handle_claude_url__failed_status__shows_info_message(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    await _create_init_task(db_sessionmaker, status="failed")
    mock_db = make_mock_database(db_sessionmaker)
    message = make_mock_message(text="https://claude.ai/login?token=test-token-failed")

    await handle_claude_url(message, mock_db)

    mock_db.write.assert_not_called()
    reply_text = message.reply.call_args[0][0]
    assert "init_session" in reply_text.lower() or "/init_session" in reply_text
