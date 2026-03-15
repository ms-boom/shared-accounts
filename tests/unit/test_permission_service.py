"""Tests for PermissionService — admin checks, caching, invalidation."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from aiogram.types import ChatMember

from bot.services.permission_service import PermissionService


@pytest.mark.unit
async def test__checks_admin_permission_via_api(
    permission_service: PermissionService,
    mock_bot: MagicMock,
    mock_admin_member: ChatMember,
) -> None:
    mock_bot.get_chat_member.return_value = mock_admin_member

    is_admin = await permission_service.is_group_admin(
        bot=mock_bot, user_id=123, chat_id=-100123456789
    )

    assert is_admin is True
    mock_bot.get_chat_member.assert_called_once_with(-100123456789, 123)


@pytest.mark.unit
async def test__recognizes_creator_as_admin(
    permission_service: PermissionService,
    mock_bot: MagicMock,
    mock_creator_member: ChatMember,
) -> None:
    mock_bot.get_chat_member.return_value = mock_creator_member

    is_admin = await permission_service.is_group_admin(
        bot=mock_bot, user_id=456, chat_id=-100123456789
    )

    assert is_admin is True


@pytest.mark.unit
async def test__recognizes_regular_member_as_not_admin(
    permission_service: PermissionService,
    mock_bot: MagicMock,
    mock_regular_member: ChatMember,
) -> None:
    mock_bot.get_chat_member.return_value = mock_regular_member

    is_admin = await permission_service.is_group_admin(
        bot=mock_bot, user_id=789, chat_id=-100123456789
    )

    assert is_admin is False


@pytest.mark.unit
async def test__caches_permission_check(
    permission_service: PermissionService,
    mock_bot: MagicMock,
    mock_admin_member: ChatMember,
) -> None:
    mock_bot.get_chat_member.return_value = mock_admin_member

    await permission_service.is_group_admin(
        bot=mock_bot, user_id=123, chat_id=-100123456789
    )
    await permission_service.is_group_admin(
        bot=mock_bot, user_id=123, chat_id=-100123456789
    )

    assert mock_bot.get_chat_member.call_count == 1


@pytest.mark.unit
async def test__cache_expires_after_ttl(
    permission_service: PermissionService,
    mock_bot: MagicMock,
    mock_admin_member: ChatMember,
) -> None:
    mock_bot.get_chat_member.return_value = mock_admin_member

    await permission_service.is_group_admin(
        bot=mock_bot, user_id=123, chat_id=-100123456789
    )

    # Expire cache manually
    cache_key = permission_service._get_cache_key(123, -100123456789)
    is_admin, _ = permission_service._cache[cache_key]
    expired_time = datetime.utcnow() - timedelta(
        seconds=permission_service.cache_ttl + 1
    )
    permission_service._cache[cache_key] = (is_admin, expired_time)

    await permission_service.is_group_admin(
        bot=mock_bot, user_id=123, chat_id=-100123456789
    )

    assert mock_bot.get_chat_member.call_count == 2


@pytest.mark.unit
async def test__different_users_have_separate_cache(
    permission_service: PermissionService,
    mock_bot: MagicMock,
    mock_admin_member: ChatMember,
) -> None:
    mock_bot.get_chat_member.return_value = mock_admin_member

    await permission_service.is_group_admin(
        bot=mock_bot, user_id=123, chat_id=-100123456789
    )
    await permission_service.is_group_admin(
        bot=mock_bot, user_id=456, chat_id=-100123456789
    )

    assert mock_bot.get_chat_member.call_count == 2


@pytest.mark.unit
async def test__different_chats_have_separate_cache(
    permission_service: PermissionService,
    mock_bot: MagicMock,
    mock_admin_member: ChatMember,
) -> None:
    mock_bot.get_chat_member.return_value = mock_admin_member

    await permission_service.is_group_admin(
        bot=mock_bot, user_id=123, chat_id=-100123456789
    )
    await permission_service.is_group_admin(
        bot=mock_bot, user_id=123, chat_id=-100987654321
    )

    assert mock_bot.get_chat_member.call_count == 2


@pytest.mark.unit
async def test__invalidates_entire_cache(
    permission_service: PermissionService,
    mock_bot: MagicMock,
    mock_admin_member: ChatMember,
) -> None:
    mock_bot.get_chat_member.return_value = mock_admin_member

    await permission_service.is_group_admin(
        bot=mock_bot, user_id=123, chat_id=-100123456789
    )
    await permission_service.is_group_admin(
        bot=mock_bot, user_id=456, chat_id=-100987654321
    )

    permission_service.invalidate_cache()
    assert len(permission_service._cache) == 0

    await permission_service.is_group_admin(
        bot=mock_bot, user_id=123, chat_id=-100123456789
    )
    assert mock_bot.get_chat_member.call_count == 3


@pytest.mark.unit
async def test__invalidates_cache_by_user_id(
    permission_service: PermissionService,
    mock_bot: MagicMock,
    mock_admin_member: ChatMember,
) -> None:
    mock_bot.get_chat_member.return_value = mock_admin_member

    await permission_service.is_group_admin(
        bot=mock_bot, user_id=123, chat_id=-100123456789
    )
    await permission_service.is_group_admin(
        bot=mock_bot, user_id=456, chat_id=-100123456789
    )

    permission_service.invalidate_cache(user_id=123)
    assert len(permission_service._cache) == 1

    await permission_service.is_group_admin(
        bot=mock_bot, user_id=123, chat_id=-100123456789
    )
    assert mock_bot.get_chat_member.call_count == 3


@pytest.mark.unit
async def test__invalidates_cache_by_chat_id(
    permission_service: PermissionService,
    mock_bot: MagicMock,
    mock_admin_member: ChatMember,
) -> None:
    mock_bot.get_chat_member.return_value = mock_admin_member

    await permission_service.is_group_admin(
        bot=mock_bot, user_id=123, chat_id=-100123456789
    )
    await permission_service.is_group_admin(
        bot=mock_bot, user_id=123, chat_id=-100987654321
    )

    permission_service.invalidate_cache(chat_id=-100123456789)
    assert len(permission_service._cache) == 1


@pytest.mark.unit
async def test__returns_false_on_api_error(
    permission_service: PermissionService,
    mock_bot: MagicMock,
) -> None:
    mock_bot.get_chat_member.side_effect = Exception("API Error")

    is_admin = await permission_service.is_group_admin(
        bot=mock_bot, user_id=123, chat_id=-100123456789
    )

    assert is_admin is False


@pytest.mark.unit
async def test__invalidates_cache_on_api_error(
    permission_service: PermissionService,
    mock_bot: MagicMock,
    mock_admin_member: ChatMember,
) -> None:
    mock_bot.get_chat_member.return_value = mock_admin_member
    await permission_service.is_group_admin(
        bot=mock_bot, user_id=123, chat_id=-100123456789
    )

    cache_key = permission_service._get_cache_key(123, -100123456789)
    assert cache_key in permission_service._cache

    permission_service.invalidate_cache()

    mock_bot.get_chat_member.side_effect = Exception("API Error")
    await permission_service.is_group_admin(
        bot=mock_bot, user_id=123, chat_id=-100123456789
    )

    assert cache_key not in permission_service._cache
