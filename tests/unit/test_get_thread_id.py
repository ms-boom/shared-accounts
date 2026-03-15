"""Tests for get_thread_id() function from claude_auth handlers."""

from unittest.mock import MagicMock

import pytest
from aiogram.types import Chat, Message, User

from bot.handlers.claude_auth import get_thread_id


@pytest.mark.unit
def test__get_thread_id__no_topic__returns_zero() -> None:
    message = MagicMock(spec=Message)
    message.message_thread_id = None

    assert get_thread_id(message) == 0


@pytest.mark.unit
def test__get_thread_id__topic_123__returns_123() -> None:
    message = MagicMock(spec=Message)
    message.message_thread_id = 123

    assert get_thread_id(message) == 123


@pytest.mark.unit
def test__get_thread_id__zero__returns_zero() -> None:
    """thread_id=0 is falsy but should be returned as-is."""
    message = MagicMock(spec=Message)
    message.message_thread_id = 0

    assert get_thread_id(message) == 0


@pytest.mark.unit
@pytest.mark.parametrize(
    ("thread_id_value", "expected"),
    [
        (None, 0),
        (1, 1),
        (999, 999),
        (123456, 123456),
    ],
)
def test__get_thread_id__various_values(thread_id_value, expected) -> None:
    message = MagicMock(spec=Message)
    message.message_thread_id = thread_id_value

    assert get_thread_id(message) == expected


@pytest.mark.unit
def test__get_thread_id__consistency_across_messages() -> None:
    messages = []
    for _ in range(3):
        msg = MagicMock(spec=Message)
        msg.message_thread_id = 777
        messages.append(msg)

    thread_ids = [get_thread_id(m) for m in messages]
    assert all(tid == 777 for tid in thread_ids)
