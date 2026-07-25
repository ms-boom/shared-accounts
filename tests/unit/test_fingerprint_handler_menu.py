"""Tests for the `/fingerprint` command — access gate and view card."""

from unittest.mock import MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ChatMember
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.handlers.fingerprint import fingerprint_handler
from bot.services.fingerprint_access_service import FingerprintAccessService
from core.services.fingerprint_resolution_service import FingerprintResolutionService
from tests.unit.conftest import make_mock_database, make_mock_message


def _state(chat_id: int, user_id: int, thread_id: int = 0) -> FSMContext:
    return FSMContext(
        storage=MemoryStorage(),
        key=StorageKey(bot_id=1, chat_id=chat_id, user_id=user_id, thread_id=thread_id),
    )


@pytest.mark.unit
async def test__fingerprint_handler__group_non_admin_is_refused(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fingerprint_resolution_service: FingerprintResolutionService,
    fingerprint_access_service: FingerprintAccessService,
    mock_regular_member: ChatMember,
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    message = make_mock_message(chat_id=-100111, user_id=789, chat_type="supergroup")
    message.bot.get_chat_member.return_value = mock_regular_member
    state = _state(-100111, 789)

    await fingerprint_handler(
        message,
        mock_db,
        fingerprint_resolution_service,
        fingerprint_access_service,
        state,
    )

    message.reply.assert_called_once()
    reply_text = message.reply.call_args.args[0]
    assert "администратор" in reply_text


@pytest.mark.unit
async def test__fingerprint_handler__group_admin_sees_menu_with_default_profile(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fingerprint_resolution_service: FingerprintResolutionService,
    fingerprint_access_service: FingerprintAccessService,
    mock_admin_member: ChatMember,
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    message = make_mock_message(chat_id=-100222, user_id=111, chat_type="supergroup")
    message.bot.get_chat_member.return_value = mock_admin_member
    state = _state(-100222, 111)

    await fingerprint_handler(
        message,
        mock_db,
        fingerprint_resolution_service,
        fingerprint_access_service,
        state,
    )

    message.reply.assert_called_once()
    reply_text = message.reply.call_args.args[0]
    assert "по умолчанию" in reply_text

    keyboard = message.reply.call_args.kwargs["reply_markup"]
    button_texts = [b.text for row in keyboard.inline_keyboard for b in row]
    assert not any("Сбросить" in t for t in button_texts)
    assert not any("Изменить для всех" in t for t in button_texts)


@pytest.mark.unit
async def test__fingerprint_handler__private_chat_owner_sees_menu(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fingerprint_resolution_service: FingerprintResolutionService,
    fingerprint_access_service: FingerprintAccessService,
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    message = make_mock_message(chat_id=555, user_id=555, chat_type="private")
    state = _state(555, 555)

    await fingerprint_handler(
        message,
        mock_db,
        fingerprint_resolution_service,
        fingerprint_access_service,
        state,
    )

    message.reply.assert_called_once()
    message.bot.get_chat_member.assert_not_called()


@pytest.mark.unit
async def test__fingerprint_handler__private_chat_foreign_user_is_refused(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fingerprint_resolution_service: FingerprintResolutionService,
    fingerprint_access_service: FingerprintAccessService,
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    message = make_mock_message(chat_id=555, user_id=999, chat_type="private")
    state = _state(555, 999)

    await fingerprint_handler(
        message,
        mock_db,
        fingerprint_resolution_service,
        fingerprint_access_service,
        state,
    )

    reply_text = message.reply.call_args.args[0]
    assert "администратор" in reply_text


@pytest.mark.unit
async def test__fingerprint_handler__shows_reset_button_when_bound(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fingerprint_resolution_service: FingerprintResolutionService,
    fingerprint_access_service: FingerprintAccessService,
    fingerprint_management_service: MagicMock,
) -> None:
    from core.fingerprint import FingerprintValues

    mock_db = make_mock_database(db_sessionmaker)

    async def _seed(session: AsyncSession) -> None:
        await fingerprint_management_service.set_own(
            session,
            333,
            0,
            values=FingerprintValues(
                user_agent="UA",
                cpu_cores=8,
                device_memory=8,
                timezone=None,
                locale=None,
            ),
            created_by=333,
        )

    await mock_db.write(_seed)

    message = make_mock_message(chat_id=333, user_id=333, chat_type="private")
    state = _state(333, 333)

    await fingerprint_handler(
        message,
        mock_db,
        fingerprint_resolution_service,
        fingerprint_access_service,
        state,
    )

    keyboard = message.reply.call_args.kwargs["reply_markup"]
    button_texts = [b.text for row in keyboard.inline_keyboard for b in row]
    assert any("Сбросить" in t for t in button_texts)
