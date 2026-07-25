"""Shared fixtures for unit tests.

Common mock factories and test helpers used across multiple test modules.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import (
    CallbackQuery,
    Chat,
    ChatMember,
    ChatMemberAdministrator,
    ChatMemberMember,
    ChatMemberOwner,
    Message,
    User,
)
from sqlalchemy import select
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
    return ChatMemberAdministrator(
        user=User(id=123, is_bot=False, first_name="Admin"),
        can_be_edited=False,
        is_anonymous=False,
        can_manage_chat=True,
        can_delete_messages=True,
        can_manage_video_chats=True,
        can_restrict_members=True,
        can_promote_members=True,
        can_change_info=True,
        can_invite_users=True,
        can_post_stories=True,
        can_edit_stories=True,
        can_delete_stories=True,
    )


@pytest.fixture
def mock_creator_member() -> ChatMember:
    """ChatMember with creator status."""
    return ChatMemberOwner(
        user=User(id=456, is_bot=False, first_name="Creator"),
        is_anonymous=False,
    )


@pytest.fixture
def mock_regular_member() -> ChatMember:
    """ChatMember with member status."""
    return ChatMemberMember(
        user=User(id=789, is_bot=False, first_name="User"),
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


_USE_DEFAULT_USER = object()  # sentinel distinguishing "unset" from an explicit None


def make_mock_message(
    *,
    chat_id: int = -100123456789,
    user_id: int = 123456789,
    text: str = "",
    chat_type: str = "private",
    thread_id: int | None = None,
    from_user: User | MagicMock | None | object = _USE_DEFAULT_USER,
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

    if from_user is _USE_DEFAULT_USER:
        message.from_user = MagicMock(spec=User)
        message.from_user.id = user_id
    else:
        message.from_user = from_user

    message.bot = MagicMock()
    message.bot.get_chat_member = AsyncMock()
    return message


def make_mock_callback(
    *,
    data: str,
    chat_id: int = -100123456789,
    user_id: int = 123456789,
    chat_type: str = "private",
    thread_id: int | None = None,
) -> MagicMock:
    """Create a mock Telegram CallbackQuery with an editable mock Message.

    This helper is NOT a fixture — call it directly in tests.
    """
    callback = MagicMock(spec=CallbackQuery)
    callback.data = data
    callback.from_user = MagicMock(spec=User)
    callback.from_user.id = user_id
    callback.answer = AsyncMock()

    message = MagicMock(spec=Message)
    message.chat = MagicMock(spec=Chat)
    message.chat.id = chat_id
    message.chat.type = chat_type
    message.message_thread_id = thread_id
    message.edit_text = AsyncMock()
    message.answer = AsyncMock()
    callback.message = message

    callback.bot = MagicMock()
    callback.bot.get_chat_member = AsyncMock()
    return callback


async def reload_fingerprint_binding(
    session_maker: async_sessionmaker[AsyncSession], chat_id: int, thread_id: int = 0
) -> dict | None:
    """Independent re-read of a fingerprint binding through a fresh session.

    Not the writer's own session — proves the write actually landed rather
    than trusting the in-memory object the write returned.

    This helper is NOT a fixture — call it directly in tests.
    """
    from core.db.models import Fingerprint, SessionFingerprint

    async with session_maker() as session:
        stmt = select(SessionFingerprint).where(
            SessionFingerprint.chat_id == chat_id,
            SessionFingerprint.thread_id == thread_id,
        )
        binding = (await session.execute(stmt)).scalar_one_or_none()
        if binding is None:
            return None
        fp = (
            await session.execute(
                select(Fingerprint).where(Fingerprint.id == binding.fingerprint_id)
            )
        ).scalar_one()
        return {
            "fingerprint_id": binding.fingerprint_id,
            "user_agent": fp.user_agent,
            "cpu_cores": fp.cpu_cores,
            "device_memory": fp.device_memory,
            "timezone": fp.timezone,
            "locale": fp.locale,
        }


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


@pytest.fixture
def fingerprint_repository(db_session: AsyncSession):
    """Create FingerprintRepository instance."""
    from core.db.repositories.fingerprint_repository import FingerprintRepository

    return FingerprintRepository(db_session)


@pytest.fixture
def session_fingerprint_repository(db_session: AsyncSession):
    """Create SessionFingerprintRepository instance."""
    from core.db.repositories.session_fingerprint_repository import (
        SessionFingerprintRepository,
    )

    return SessionFingerprintRepository(db_session)


@pytest.fixture
def fingerprint_resolution_service(test_settings: Settings):
    """Create FingerprintResolutionService instance."""
    from core.services.fingerprint_resolution_service import (
        FingerprintResolutionService,
    )

    return FingerprintResolutionService(test_settings)


@pytest.fixture
def fingerprint_management_service():
    """Create FingerprintManagementService instance (stateless, session-agnostic)."""
    from core.services.fingerprint_management_service import (
        FingerprintManagementService,
    )

    return FingerprintManagementService()


@pytest.fixture
def fingerprint_access_service(permission_service):
    """Create FingerprintAccessService instance."""
    from bot.services.fingerprint_access_service import FingerprintAccessService

    return FingerprintAccessService(permission_service)
