"""Tests for topic isolation logic in bot/handlers/claude_auth.py."""

from unittest.mock import MagicMock

import pytest
from aiogram.types import Chat, Message

from bot.handlers.claude_auth import get_thread_id


@pytest.mark.unit
def test_different_topics_have_different_thread_ids() -> None:
    """Test that different topics have different thread_ids."""
    # Create messages for different topics
    topic1_message = MagicMock(spec=Message)
    topic1_message.message_thread_id = 100

    topic2_message = MagicMock(spec=Message)
    topic2_message.message_thread_id = 200

    main_message = MagicMock(spec=Message)
    main_message.message_thread_id = None

    # Extract thread_ids
    topic1_id = get_thread_id(topic1_message)
    topic2_id = get_thread_id(topic2_message)
    main_id = get_thread_id(main_message)

    # All should be different
    assert topic1_id == 100
    assert topic2_id == 200
    assert main_id == 0
    assert len({topic1_id, topic2_id, main_id}) == 3


@pytest.mark.unit
def test_same_chat_different_topics_isolated() -> None:
    """Test that same chat_id with different topics are isolated."""
    chat_id = -100123456789

    # Main chat message
    main_msg = MagicMock(spec=Message)
    main_msg.message_thread_id = None
    main_msg.chat = MagicMock(spec=Chat)
    main_msg.chat.id = chat_id

    # Topic message
    topic_msg = MagicMock(spec=Message)
    topic_msg.message_thread_id = 999
    topic_msg.chat = MagicMock(spec=Chat)
    topic_msg.chat.id = chat_id

    # Same chat_id, different thread_ids
    assert main_msg.chat.id == topic_msg.chat.id
    assert get_thread_id(main_msg) != get_thread_id(topic_msg)
