"""Tests verifying get_code_handler routes writes through db.write()."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.handlers.claude_auth import get_code_handler
from core.db.repositories.chat_session_repository import ChatSessionRepository
from tests.unit.conftest import make_mock_database, make_mock_message


@pytest.mark.unit
async def test__get_code_handler__creates_task_through_write(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    mock_db = make_mock_database(db_sessionmaker)

    # Create a chat session so get_code_handler finds it
    async with db_sessionmaker() as session, session.begin():
        repo = ChatSessionRepository(session)
        await repo.create(
            chat_id=-100123456789,
            email="test@example.com",
            session_path="/data/sessions/test",
        )

    message = make_mock_message(
        text="/get_code https://claude.ai/auth/authorize?test=1"
    )

    await get_code_handler(message, mock_db)

    mock_db.write.assert_called_once()
    message.reply.assert_called()


@pytest.mark.unit
async def test__get_code_handler__no_session__no_write_call(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    message = make_mock_message(
        text="/get_code https://claude.ai/auth/authorize?test=1"
    )

    await get_code_handler(message, mock_db)

    mock_db.write.assert_not_called()
