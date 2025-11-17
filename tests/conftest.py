"""Global test configuration and fixtures.

This module configures pytest for the test infrastructure and imports
modular fixtures from the fixtures/ directory.

IMPORTANT: Modular fixtures are loaded in specific order to ensure
proper initialization of session-scoped async resources.
"""

import os
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from aiogram import Bot
from aiogram.types import Chat, ChatMember, User

# Configure asyncio mode for pytest-asyncio
# IMPORTANT: environment must be first to load event_loop fixture before async fixtures
pytest_plugins = [
    "tests.fixtures.environment",
    "tests.fixtures.database",
]


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """
    Create temporary directory for tests.

    Args:
        tmp_path: pytest's temporary directory fixture

    Returns:
        Path to temporary directory
    """
    return tmp_path


@pytest.fixture
def mock_bot() -> MagicMock:
    """
    Create mock Bot instance.

    Returns:
        Mocked Bot with common methods
    """
    bot = MagicMock(spec=Bot)
    bot.get_chat_member = AsyncMock()
    bot.send_message = AsyncMock()
    return bot


@pytest.fixture
def telegram_user() -> User:
    """
    Create mock Telegram user.

    Returns:
        User instance for testing
    """
    return User(
        id=123456789,
        is_bot=False,
        first_name="Test",
        last_name="User",
        username="testuser",
        language_code="en",
    )


@pytest.fixture
def telegram_chat() -> Chat:
    """
    Create mock Telegram chat.

    Returns:
        Chat instance for testing
    """
    return Chat(
        id=-100123456789,
        type="supergroup",
        title="Test Group",
    )


@pytest.fixture
def admin_chat_member(telegram_user: User) -> ChatMemberAdministrator:
    """
    Create admin ChatMemberAdministrator.

    Args:
        telegram_user: Telegram user fixture

    Returns:
        ChatMemberAdministrator with admin permissions
    """
    return ChatMemberAdministrator(
        user=telegram_user,
        status=ChatMemberStatus.ADMINISTRATOR,
        can_be_edited=False,
        is_anonymous=False,
        can_manage_chat=True,
        can_delete_messages=True,
        can_manage_video_chats=True,
        can_restrict_members=True,
        can_promote_members=False,
        can_change_info=True,
        can_invite_users=True,
        can_post_stories=False,
        can_edit_stories=False,
        can_delete_stories=False,
        can_post_messages=None,
        can_edit_messages=None,
        can_pin_messages=True,
        can_manage_topics=True,
        can_manage_direct_messages=False,
    )


@pytest.fixture
def regular_chat_member(telegram_user: User) -> ChatMemberMember:
    """
    Create regular ChatMemberMember.

    Args:
        telegram_user: Telegram user fixture

    Returns:
        ChatMemberMember with member status
    """
    return ChatMemberMember(
        user=telegram_user,
        status=ChatMemberStatus.MEMBER,
    )


@pytest.fixture
def task_id() -> str:
    """
    Generate unique task ID.

    Returns:
        UUID string for task testing
    """
    return str(uuid4())


@pytest.fixture
def sample_task_payload() -> dict[str, Any]:
    """
    Create sample task payload.

    Returns:
        Task payload for testing
    """
    return {
        "email": "test@example.com",
        "action": "init_session",
    }
