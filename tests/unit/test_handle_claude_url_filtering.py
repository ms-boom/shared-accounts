"""Tests for handle_claude_url — message filtering logic."""

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
async def test__handle_claude_url__no_text__returns_silently(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    message = make_mock_message(text="")
    message.text = None

    await handle_claude_url(message, mock_db)

    message.reply.assert_not_called()
    mock_db.write.assert_not_called()


@pytest.mark.unit
async def test__handle_claude_url__non_claude_url__returns_silently(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    message = make_mock_message(text="https://google.com/some-page")

    await handle_claude_url(message, mock_db)

    message.reply.assert_not_called()
    mock_db.write.assert_not_called()


@pytest.mark.unit
async def test__handle_claude_url__plain_text__returns_silently(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    message = make_mock_message(text="Hello, this is a regular message")

    await handle_claude_url(message, mock_db)

    message.reply.assert_not_called()
    mock_db.write.assert_not_called()


@pytest.mark.unit
async def test__handle_claude_url__magic_link_url__creates_task(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    await _create_init_task(db_sessionmaker, status="done")
    mock_db = make_mock_database(db_sessionmaker)
    message = make_mock_message(text="https://claude.ai/magic-link#some-token")

    await handle_claude_url(message, mock_db)

    mock_db.write.assert_called_once()


@pytest.mark.unit
async def test__handle_claude_url__no_init_task__shows_info(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    message = make_mock_message(text="https://claude.ai/login?token=orphan-token")

    await handle_claude_url(message, mock_db)

    mock_db.write.assert_not_called()
    message.reply.assert_called_once()
    reply_text = message.reply.call_args[0][0]
    assert "/init_session" in reply_text


@pytest.mark.unit
async def test__handle_claude_url__no_from_user__returns_error(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    await _create_init_task(db_sessionmaker, status="done")
    mock_db = make_mock_database(db_sessionmaker)
    message = make_mock_message(
        text="https://claude.ai/login?token=test-token",
        from_user=None,
    )

    await handle_claude_url(message, mock_db)

    mock_db.write.assert_not_called()
    reply_text = message.reply.call_args[0][0]
    assert "Unable to identify user" in reply_text
