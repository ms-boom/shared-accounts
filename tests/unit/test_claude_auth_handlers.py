"""Unit tests for bot/handlers/claude_auth.py."""

from unittest.mock import MagicMock

import pytest
from aiogram.types import Chat, Message, User

from bot.handlers.claude_auth import get_thread_id
from core.services.validation_service import ValidationService

# Wrapper for backward compatibility with existing tests
validate_email = ValidationService.validate_email


@pytest.mark.unit
class TestGetThreadId:
    """Tests for get_thread_id() function."""

    def test_returns_zero_for_main_chat(self) -> None:
        """Test get_thread_id returns 0 for main chat (no topic)."""
        # Create message without message_thread_id
        message = MagicMock(spec=Message)
        message.message_thread_id = None

        thread_id = get_thread_id(message)

        assert thread_id == 0

    def test_returns_thread_id_for_topic(self) -> None:
        """Test get_thread_id returns actual thread_id for topics."""
        # Create message with message_thread_id
        message = MagicMock(spec=Message)
        message.message_thread_id = 123

        thread_id = get_thread_id(message)

        assert thread_id == 123

    def test_handles_various_thread_ids(self) -> None:
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

    def test_handles_zero_thread_id(self) -> None:
        """Test get_thread_id handles thread_id=0 correctly."""
        message = MagicMock(spec=Message)
        message.message_thread_id = 0

        thread_id = get_thread_id(message)

        # 0 is falsy, but should be returned as-is
        assert thread_id == 0


@pytest.mark.unit
class TestValidateEmail:
    """Tests for validate_email() function."""

    def test_valid_email_formats(self) -> None:
        """Test validate_email accepts valid email formats."""
        valid_emails = [
            "test@example.com",
            "user.name@example.com",
            "user+tag@example.co.uk",
            "first.last@subdomain.example.com",
            "123@example.com",
            "user_name@example.com",
        ]

        for email in valid_emails:
            assert validate_email(email), f"Should accept {email}"

    def test_invalid_email_formats(self) -> None:
        """Test validate_email rejects invalid email formats."""
        invalid_emails = [
            "",
            "not-an-email",
            "@example.com",
            "user@",
            "user @example.com",  # Space
            "user@example",  # No TLD
        ]

        for email in invalid_emails:
            assert not validate_email(email), f"Should reject {email}"

    def test_email_with_special_characters(self) -> None:
        """Test validate_email handles special characters."""
        # Valid special characters
        assert validate_email("user+filter@example.com")
        assert validate_email("user.name@example.com")
        assert validate_email("user_name@example.com")

        # Invalid special characters
        assert not validate_email("user@example@com")
        assert not validate_email("user name@example.com")


@pytest.mark.unit
class TestHandlerIntegration:
    """Integration tests for handlers with thread_id."""

    @pytest.fixture
    def mock_message_main_chat(self) -> MagicMock:
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
    def mock_message_topic(self) -> MagicMock:
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

    def test_get_thread_id_from_main_chat_message(
        self, mock_message_main_chat: MagicMock
    ) -> None:
        """Test extracting thread_id from main chat message."""
        thread_id = get_thread_id(mock_message_main_chat)
        assert thread_id == 0

    def test_get_thread_id_from_topic_message(
        self, mock_message_topic: MagicMock
    ) -> None:
        """Test extracting thread_id from topic message."""
        thread_id = get_thread_id(mock_message_topic)
        assert thread_id == 555

    def test_thread_id_consistency_across_messages(self) -> None:
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


@pytest.mark.unit
class TestTopicIsolation:
    """Tests for topic isolation logic."""

    def test_different_topics_have_different_thread_ids(self) -> None:
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

    def test_same_chat_different_topics_isolated(self) -> None:
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
