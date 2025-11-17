"""Unit tests for bot/services/permission_service.py."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from aiogram.types import ChatMember, User

from bot.core.config import Settings
from bot.services.permission_service import PermissionService


@pytest.fixture
def permission_service(test_settings: Settings) -> PermissionService:
    """
    Create PermissionService instance for testing.

    Args:
        test_settings: Test settings fixture

    Returns:
        PermissionService instance
    """
    return PermissionService(test_settings)


@pytest.fixture
def mock_admin_member() -> ChatMember:
    """
    Create mock admin ChatMember.

    Returns:
        ChatMember with administrator status
    """
    return ChatMember(
        user=User(id=123, is_bot=False, first_name="Admin"),
        status="administrator",
    )


@pytest.fixture
def mock_creator_member() -> ChatMember:
    """
    Create mock creator ChatMember.

    Returns:
        ChatMember with creator status
    """
    return ChatMember(
        user=User(id=456, is_bot=False, first_name="Creator"),
        status="creator",
    )


@pytest.fixture
def mock_regular_member() -> ChatMember:
    """
    Create mock regular ChatMember.

    Returns:
        ChatMember with member status
    """
    return ChatMember(
        user=User(id=789, is_bot=False, first_name="User"),
        status="member",
    )


@pytest.mark.unit
async def test_checks_admin_permission_via_api(
    permission_service: PermissionService,
    mock_bot: MagicMock,
    mock_admin_member: ChatMember,
) -> None:
    """Test that admin permission check calls Telegram API."""
    mock_bot.get_chat_member.return_value = mock_admin_member

    is_admin = await permission_service.is_group_admin(
        bot=mock_bot,
        user_id=123,
        chat_id=-100123456789,
    )

    assert is_admin is True
    mock_bot.get_chat_member.assert_called_once_with(-100123456789, 123)


@pytest.mark.unit
async def test_recognizes_creator_as_admin(
    permission_service: PermissionService,
    mock_bot: MagicMock,
    mock_creator_member: ChatMember,
) -> None:
    """Test that creator status is recognized as admin."""
    mock_bot.get_chat_member.return_value = mock_creator_member

    is_admin = await permission_service.is_group_admin(
        bot=mock_bot,
        user_id=456,
        chat_id=-100123456789,
    )

    assert is_admin is True


@pytest.mark.unit
async def test_recognizes_regular_member_as_not_admin(
    permission_service: PermissionService,
    mock_bot: MagicMock,
    mock_regular_member: ChatMember,
) -> None:
    """Test that regular member is not recognized as admin."""
    mock_bot.get_chat_member.return_value = mock_regular_member

    is_admin = await permission_service.is_group_admin(
        bot=mock_bot,
        user_id=789,
        chat_id=-100123456789,
    )

    assert is_admin is False


@pytest.mark.unit
async def test_caches_permission_check(
    permission_service: PermissionService,
    mock_bot: MagicMock,
    mock_admin_member: ChatMember,
) -> None:
    """Test that permission checks are cached."""
    mock_bot.get_chat_member.return_value = mock_admin_member

    # First call - should hit API
    await permission_service.is_group_admin(
        bot=mock_bot,
        user_id=123,
        chat_id=-100123456789,
    )

    # Second call - should use cache
    await permission_service.is_group_admin(
        bot=mock_bot,
        user_id=123,
        chat_id=-100123456789,
    )

    # API should be called only once
    assert mock_bot.get_chat_member.call_count == 1


@pytest.mark.unit
async def test_cache_expires_after_ttl(
    permission_service: PermissionService,
    mock_bot: MagicMock,
    mock_admin_member: ChatMember,
) -> None:
    """Test that cache expires after TTL."""
    mock_bot.get_chat_member.return_value = mock_admin_member

    # First call
    await permission_service.is_group_admin(
        bot=mock_bot,
        user_id=123,
        chat_id=-100123456789,
    )

    # Manually expire cache by modifying timestamp
    cache_key = permission_service._get_cache_key(123, -100123456789)
    is_admin, _ = permission_service._cache[cache_key]
    expired_time = datetime.utcnow() - timedelta(
        seconds=permission_service.cache_ttl + 1
    )
    permission_service._cache[cache_key] = (is_admin, expired_time)

    # Second call - should hit API again
    await permission_service.is_group_admin(
        bot=mock_bot,
        user_id=123,
        chat_id=-100123456789,
    )

    # API should be called twice
    assert mock_bot.get_chat_member.call_count == 2


@pytest.mark.unit
async def test_different_users_have_separate_cache(
    permission_service: PermissionService,
    mock_bot: MagicMock,
    mock_admin_member: ChatMember,
) -> None:
    """Test that different users have separate cache entries."""
    mock_bot.get_chat_member.return_value = mock_admin_member

    # Check for user 123
    await permission_service.is_group_admin(
        bot=mock_bot,
        user_id=123,
        chat_id=-100123456789,
    )

    # Check for user 456
    await permission_service.is_group_admin(
        bot=mock_bot,
        user_id=456,
        chat_id=-100123456789,
    )

    # API should be called twice (different users)
    assert mock_bot.get_chat_member.call_count == 2


@pytest.mark.unit
async def test_different_chats_have_separate_cache(
    permission_service: PermissionService,
    mock_bot: MagicMock,
    mock_admin_member: ChatMember,
) -> None:
    """Test that different chats have separate cache entries."""
    mock_bot.get_chat_member.return_value = mock_admin_member

    # Check in chat 1
    await permission_service.is_group_admin(
        bot=mock_bot,
        user_id=123,
        chat_id=-100123456789,
    )

    # Check in chat 2
    await permission_service.is_group_admin(
        bot=mock_bot,
        user_id=123,
        chat_id=-100987654321,
    )

    # API should be called twice (different chats)
    assert mock_bot.get_chat_member.call_count == 2


@pytest.mark.unit
async def test_invalidates_entire_cache(
    permission_service: PermissionService,
    mock_bot: MagicMock,
    mock_admin_member: ChatMember,
) -> None:
    """Test clearing entire cache."""
    mock_bot.get_chat_member.return_value = mock_admin_member

    # Create cache entries
    await permission_service.is_group_admin(
        bot=mock_bot,
        user_id=123,
        chat_id=-100123456789,
    )

    await permission_service.is_group_admin(
        bot=mock_bot,
        user_id=456,
        chat_id=-100987654321,
    )

    # Invalidate entire cache
    permission_service.invalidate_cache()

    assert len(permission_service._cache) == 0

    # Next call should hit API
    await permission_service.is_group_admin(
        bot=mock_bot,
        user_id=123,
        chat_id=-100123456789,
    )

    assert mock_bot.get_chat_member.call_count == 3


@pytest.mark.unit
async def test_invalidates_cache_by_user_id(
    permission_service: PermissionService,
    mock_bot: MagicMock,
    mock_admin_member: ChatMember,
) -> None:
    """Test invalidating cache for specific user."""
    mock_bot.get_chat_member.return_value = mock_admin_member

    # Create cache entries for different users
    await permission_service.is_group_admin(
        bot=mock_bot,
        user_id=123,
        chat_id=-100123456789,
    )

    await permission_service.is_group_admin(
        bot=mock_bot,
        user_id=456,
        chat_id=-100123456789,
    )

    # Invalidate only user 123
    permission_service.invalidate_cache(user_id=123)

    # Cache for user 123 should be gone, but user 456 should remain
    assert len(permission_service._cache) == 1

    # Next call for user 123 should hit API
    await permission_service.is_group_admin(
        bot=mock_bot,
        user_id=123,
        chat_id=-100123456789,
    )

    assert mock_bot.get_chat_member.call_count == 3


@pytest.mark.unit
async def test_invalidates_cache_by_chat_id(
    permission_service: PermissionService,
    mock_bot: MagicMock,
    mock_admin_member: ChatMember,
) -> None:
    """Test invalidating cache for specific chat."""
    mock_bot.get_chat_member.return_value = mock_admin_member

    # Create cache entries for different chats
    await permission_service.is_group_admin(
        bot=mock_bot,
        user_id=123,
        chat_id=-100123456789,
    )

    await permission_service.is_group_admin(
        bot=mock_bot,
        user_id=123,
        chat_id=-100987654321,
    )

    # Invalidate only chat -100123456789
    permission_service.invalidate_cache(chat_id=-100123456789)

    # Cache for chat -100123456789 should be gone
    assert len(permission_service._cache) == 1


@pytest.mark.unit
async def test_returns_false_on_api_error(
    permission_service: PermissionService,
    mock_bot: MagicMock,
) -> None:
    """Test that API errors return False."""
    mock_bot.get_chat_member.side_effect = Exception("API Error")

    is_admin = await permission_service.is_group_admin(
        bot=mock_bot,
        user_id=123,
        chat_id=-100123456789,
    )

    assert is_admin is False


@pytest.mark.unit
async def test_invalidates_cache_on_api_error(
    permission_service: PermissionService,
    mock_bot: MagicMock,
    mock_admin_member: ChatMember,
) -> None:
    """Test that cache is invalidated on API error."""
    # First successful call
    mock_bot.get_chat_member.return_value = mock_admin_member
    await permission_service.is_group_admin(
        bot=mock_bot,
        user_id=123,
        chat_id=-100123456789,
    )

    cache_key = permission_service._get_cache_key(123, -100123456789)
    assert cache_key in permission_service._cache

    # Manually invalidate cache to force API call on next request
    permission_service.invalidate_cache()

    # Second call with error should not populate cache
    mock_bot.get_chat_member.side_effect = Exception("API Error")
    await permission_service.is_group_admin(
        bot=mock_bot,
        user_id=123,
        chat_id=-100123456789,
    )

    # Cache should remain empty (not repopulated due to error)
    assert cache_key not in permission_service._cache
