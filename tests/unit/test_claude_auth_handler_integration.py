"""Integration tests for handlers with thread_id in bot/handlers/claude_auth.py."""

from unittest.mock import MagicMock

import pytest
from aiogram.types import Chat, Message, User

from bot.handlers.claude_auth import get_thread_id


@pytest.fixture
def mock_message_main_chat() -> MagicMock:
    """Create mock message for main chat (no topic)."""
    message = MagicMock(spec=Message)
    message.message_thread_id = None
    message.chat = MagicMock(spec=Chat)
    message.chat.id = -100123456789
    message.chat.type = "supergroup"
    message.from_user = MagicMock(spec=User)
    message.from_user.id = 123456789
    message.text = "/init_session test@example.com"
    return message


@pytest.fixture
def mock_message_topic() -> MagicMock:
    """Create mock message for topic."""
    message = MagicMock(spec=Message)
    message.message_thread_id = 555
    message.chat = MagicMock(spec=Chat)
    message.chat.id = -100123456789
    message.chat.type = "supergroup"
    message.from_user = MagicMock(spec=User)
    message.from_user.id = 123456789
    message.text = "/init_session topic@example.com"
    return message


@pytest.mark.unit
def test_get_thread_id_from_main_chat_message(
    mock_message_main_chat: MagicMock,
) -> None:
    """Test extracting thread_id from main chat message."""
    thread_id = get_thread_id(mock_message_main_chat)
    assert thread_id == 0


@pytest.mark.unit
def test_get_thread_id_from_topic_message(mock_message_topic: MagicMock) -> None:
    """Test extracting thread_id from topic message."""
    thread_id = get_thread_id(mock_message_topic)
    assert thread_id == 555


@pytest.mark.unit
def test_thread_id_consistency_across_messages() -> None:
    """Test thread_id extraction is consistent."""
    # Create multiple messages with same thread_id
    messages = []
    for _ in range(3):
        message = MagicMock(spec=Message)
        message.message_thread_id = 777
        messages.append(message)

    # All should return same thread_id
    thread_ids = [get_thread_id(msg) for msg in messages]
    assert all(tid == 777 for tid in thread_ids)
