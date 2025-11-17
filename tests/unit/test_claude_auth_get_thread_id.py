"""Unit tests for get_thread_id() function in bot/handlers/claude_auth.py."""

from unittest.mock import MagicMock

import pytest
from aiogram.types import Message

from bot.handlers.claude_auth import get_thread_id


@pytest.mark.unit
def test_returns_zero_for_main_chat() -> None:
    """Test get_thread_id returns 0 for main chat (no topic)."""
    # Create message without message_thread_id
    message = MagicMock(spec=Message)
    message.message_thread_id = None

    thread_id = get_thread_id(message)

    assert thread_id == 0


@pytest.mark.unit
def test_returns_thread_id_for_topic() -> None:
    """Test get_thread_id returns actual thread_id for topics."""
    # Create message with message_thread_id
    message = MagicMock(spec=Message)
    message.message_thread_id = 123

    thread_id = get_thread_id(message)

    assert thread_id == 123


@pytest.mark.unit
def test_handles_various_thread_ids() -> None:
    """Test get_thread_id handles different thread_id values."""
    message = MagicMock(spec=Message)

    # Test with different thread IDs
    test_cases = [
        (None, 0),  # None -> 0
        (1, 1),
        (999, 999),
        (123456, 123456),
    ]

    for thread_id_value, expected in test_cases:
        message.message_thread_id = thread_id_value
        result = get_thread_id(message)
        assert result == expected, f"Failed for {thread_id_value}"


@pytest.mark.unit
def test_handles_zero_thread_id() -> None:
    """Test get_thread_id handles thread_id=0 correctly."""
    message = MagicMock(spec=Message)
    message.message_thread_id = 0

    thread_id = get_thread_id(message)

    # 0 is falsy, but should be returned as-is
    assert thread_id == 0
