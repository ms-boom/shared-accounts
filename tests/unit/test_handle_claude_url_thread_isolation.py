"""Tests for handle_claude_url — topic/thread isolation."""

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
async def test__handle_claude_url__different_thread__no_match(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """Task in thread 0 should not match message in thread 555."""
    await _create_init_task(db_sessionmaker, thread_id=0, status="done")
    mock_db = make_mock_database(db_sessionmaker)
    message = make_mock_message(
        text="https://claude.ai/login?token=thread-test",
        thread_id=555,
    )

    await handle_claude_url(message, mock_db)

    mock_db.write.assert_not_called()
    message.reply.assert_called_once()
    reply_text = message.reply.call_args[0][0]
    assert "/init_session" in reply_text


@pytest.mark.unit
async def test__handle_claude_url__same_thread__matches(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """Task in thread 555 should match message in thread 555."""
    await _create_init_task(db_sessionmaker, thread_id=555, status="done")
    mock_db = make_mock_database(db_sessionmaker)
    message = make_mock_message(
        text="https://claude.ai/login?token=thread-match",
        thread_id=555,
    )

    await handle_claude_url(message, mock_db)

    mock_db.write.assert_called_once()
