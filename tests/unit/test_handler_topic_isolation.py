"""Tests for topic isolation logic in handlers."""

from unittest.mock import MagicMock

import pytest
from aiogram.types import Chat, Message

from bot.handlers.claude_auth import get_thread_id


@pytest.mark.unit
def test__different_topics__different_thread_ids() -> None:
    topic1 = MagicMock(spec=Message)
    topic1.message_thread_id = 100

    topic2 = MagicMock(spec=Message)
    topic2.message_thread_id = 200

    main = MagicMock(spec=Message)
    main.message_thread_id = None

    ids = {get_thread_id(topic1), get_thread_id(topic2), get_thread_id(main)}
    assert ids == {100, 200, 0}


@pytest.mark.unit
def test__same_chat_different_topics__isolated() -> None:
    chat_id = -100123456789

    main_msg = MagicMock(spec=Message)
    main_msg.message_thread_id = None
    main_msg.chat = MagicMock(spec=Chat)
    main_msg.chat.id = chat_id

    topic_msg = MagicMock(spec=Message)
    topic_msg.message_thread_id = 999
    topic_msg.chat = MagicMock(spec=Chat)
    topic_msg.chat.id = chat_id

    assert main_msg.chat.id == topic_msg.chat.id
    assert get_thread_id(main_msg) != get_thread_id(topic_msg)
