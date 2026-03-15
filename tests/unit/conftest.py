"""Shared fixtures for unit tests.

Common mock factories and test helpers used across multiple test modules.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Chat, ChatMember, Message, User
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.config import Settings
from core.db.database import Database


# ---------------------------------------------------------------------------
# Telegram mocks
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_message() -> MagicMock:
    """Create a basic mock Telegram Message (no topic)."""
    message = MagicMock(spec=Message)
    message.message_thread_id = None
    message.chat = MagicMock(spec=Chat)
    message.chat.id = -100123456789
    message.chat.type = "supergroup"
    message.from_user = MagicMock(spec=User)
    message.from_user.id = 123456789
    message.text = ""
    message.reply = AsyncMock()
    message.bot = MagicMock()
    message.bot.get_chat_member = AsyncMock()
    return message


@pytest.fixture
def mock_admin_member() -> ChatMember:
    """ChatMember with administrator status."""
    return ChatMember(
        user=User(id=123, is_bot=False, first_name="Admin"),
        status="administrator",
    )


@pytest.fixture
def mock_creator_member() -> ChatMember:
    """ChatMember with creator status."""
    return ChatMember(
        user=User(id=456, is_bot=False, first_name="Creator"),
        status="creator",
    )


@pytest.fixture
def mock_regular_member() -> ChatMember:
    """ChatMember with member status."""
    return ChatMember(
        user=User(id=789, is_bot=False, first_name="User"),
        status="member",
    )


# ---------------------------------------------------------------------------
# Database mocks
# ---------------------------------------------------------------------------


def make_mock_database(
    session_maker: async_sessionmaker[AsyncSession],
) -> MagicMock:
    """Create a mock Database with real session_maker and db.write/read mocks.

    This helper is NOT a fixture — call it directly in tests that need it.
    """

    async def _write(fn):  # noqa: ANN001
        async with session_maker() as session, session.begin():
            return await fn(session)

    mock_db = MagicMock(spec=Database)
    mock_db.session_maker = session_maker
    mock_db.write = AsyncMock(side_effect=_write)
    mock_db.read = session_maker
    return mock_db


def make_mock_message(
    *,
    chat_id: int = -100123456789,
    user_id: int = 123456789,
    text: str = "",
    chat_type: str = "private",
    thread_id: int | None = None,
    from_user: User | MagicMock | None = "default",
) -> MagicMock:
    """Create a mock Telegram Message with full control over fields.

    This helper is NOT a fixture — call it directly in tests.
    """
    message = MagicMock(spec=Message)
    message.chat = MagicMock(spec=Chat)
    message.chat.id = chat_id
    message.chat.type = chat_type
    message.text = text
    message.message_thread_id = thread_id
    message.reply = AsyncMock()

    if from_user == "default":
        message.from_user = MagicMock(spec=User)
        message.from_user.id = user_id
    else:
        message.from_user = from_user

    message.bot = MagicMock()
    message.bot.get_chat_member = AsyncMock()
    return message


# ---------------------------------------------------------------------------
# Service fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def permission_service(test_settings: Settings):
    """Create PermissionService instance."""
    from bot.services.permission_service import PermissionService

    return PermissionService(test_settings)


@pytest.fixture
def user_repository(db_session: AsyncSession):
    """Create UserRepository instance."""
    from core.db.repositories.user_repository import UserRepository

    return UserRepository(db_session)


@pytest.fixture
def task_repository(db_session: AsyncSession):
    """Create TaskRepository instance."""
    from core.db.repositories.task_repository import TaskRepository

    return TaskRepository(db_session)


@pytest.fixture
def chat_session_repository(db_session: AsyncSession):
    """Create ChatSessionRepository instance."""
    from core.db.repositories.chat_session_repository import ChatSessionRepository

    return ChatSessionRepository(db_session)


@pytest.fixture
def user_service(db_sessionmaker: async_sessionmaker[AsyncSession]):
    """Create UserService with mock Database wrapping real session."""
    from core.services.user_service import UserService

    mock_db = make_mock_database(db_sessionmaker)
    return UserService(mock_db)
