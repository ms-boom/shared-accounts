"""Tests verifying init_session_handler routes writes through db.write()."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.handlers.claude_auth import init_session_handler
from core.config import Settings
from tests.unit.conftest import make_mock_database, make_mock_message


@pytest.mark.unit
async def test__init_session_handler__creates_task_through_write(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    message = make_mock_message(text="/init_session test@example.com")
    settings = MagicMock(spec=Settings)

    await init_session_handler(message, mock_db, settings)

    mock_db.write.assert_called_once()
    message.reply.assert_called()


@pytest.mark.unit
async def test__init_session_handler__task_persisted_in_db(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    message = make_mock_message(text="/init_session test@example.com")
    settings = MagicMock(spec=Settings)

    await init_session_handler(message, mock_db, settings)

    from core.db.repositories.task_repository import TaskRepository

    async with db_sessionmaker() as session:
        repo = TaskRepository(session)
        tasks = await repo.get_by_chat_id(message.chat.id, thread_id=0)
        assert len(tasks) == 1
        assert tasks[0]["task_type"] == "init_session"
        assert tasks[0]["payload"]["email"] == "test@example.com"
