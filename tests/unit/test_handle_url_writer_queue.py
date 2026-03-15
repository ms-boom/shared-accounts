"""Tests verifying handle_claude_url routes writes through db.write()."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.handlers.claude_auth import handle_claude_url
from core.db.repositories.task_repository import TaskRepository
from tests.unit.conftest import make_mock_database, make_mock_message


@pytest.mark.unit
async def test__handle_claude_url__creates_task_through_write(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    mock_db = make_mock_database(db_sessionmaker)

    # Create a pending init_session task
    async with db_sessionmaker() as session, session.begin():
        repo = TaskRepository(session)
        await repo.create(
            chat_id=-100123456789,
            user_id=123456789,
            task_type="init_session",
            payload={"email": "test@example.com"},
            thread_id=0,
        )

    message = make_mock_message(
        text="https://claude.ai/login?token=test-login-token-123"
    )

    await handle_claude_url(message, mock_db)

    mock_db.write.assert_called_once()
    message.reply.assert_called()
