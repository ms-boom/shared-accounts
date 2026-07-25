"""Tests for the copy-from-my-session picker and the reset action."""

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ChatMember
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.handlers.fingerprint import (
    pick_copy_source_handler,
    reset_handler,
    start_copy_handler,
)
from bot.services.fingerprint_access_service import FingerprintAccessService
from bot.states.fingerprint import FingerprintStates
from core.db.models import SessionFingerprint
from core.fingerprint import FingerprintValues
from core.services.fingerprint_management_service import FingerprintManagementService
from core.services.fingerprint_resolution_service import FingerprintResolutionService
from tests.unit.conftest import (
    make_mock_callback,
    make_mock_database,
    reload_fingerprint_binding,
)

EMPTY_VALUES = FingerprintValues(
    user_agent=None, cpu_cores=None, device_memory=None, timezone=None, locale=None
)


def _state(chat_id: int, user_id: int, thread_id: int = 0) -> FSMContext:
    return FSMContext(
        storage=MemoryStorage(),
        key=StorageKey(bot_id=1, chat_id=chat_id, user_id=user_id, thread_id=thread_id),
    )


async def _binding_exists(
    db_sessionmaker: async_sessionmaker[AsyncSession], chat_id: int, thread_id: int = 0
) -> bool:
    async with db_sessionmaker() as session:
        stmt = select(SessionFingerprint).where(
            SessionFingerprint.chat_id == chat_id,
            SessionFingerprint.thread_id == thread_id,
        )
        return (await session.execute(stmt)).scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# start_copy_handler — picker only lists owned sources
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test__copy_handler__lists_only_owned_sources(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fingerprint_access_service: FingerprintAccessService,
    fingerprint_management_service: FingerprintManagementService,
    mock_admin_member: ChatMember,
    mock_regular_member: ChatMember,
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    user_id = 111

    async def _seed(session: AsyncSession) -> None:
        await fingerprint_management_service.set_own(
            session, -100111, 0, values=EMPTY_VALUES, created_by=user_id
        )
        await fingerprint_management_service.set_own(
            session, -100222, 0, values=EMPTY_VALUES, created_by=999
        )

    await mock_db.write(_seed)

    callback = make_mock_callback(
        data="fp:copy", chat_id=333, user_id=user_id, chat_type="private"
    )

    async def _get_chat_member(chat_id: int, uid: int) -> ChatMember:
        return mock_admin_member if chat_id == -100111 else mock_regular_member

    callback.bot.get_chat_member.side_effect = _get_chat_member

    state = _state(333, user_id)
    await start_copy_handler(callback, mock_db, fingerprint_access_service, state)

    assert await state.get_state() == FingerprintStates.selecting_copy_source.state
    keyboard = callback.message.edit_text.call_args.kwargs["reply_markup"]
    callback_datas = [b.callback_data for row in keyboard.inline_keyboard for b in row]
    assert any("-100111" in cd for cd in callback_datas if cd)
    assert not any("-100222" in cd for cd in callback_datas if cd)


@pytest.mark.unit
async def test__copy_handler__empty_list_shows_nothing_to_copy_message(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fingerprint_access_service: FingerprintAccessService,
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    callback = make_mock_callback(
        data="fp:copy", chat_id=444, user_id=444, chat_type="private"
    )
    state = _state(444, 444)

    await start_copy_handler(callback, mock_db, fingerprint_access_service, state)

    assert await state.get_state() is None
    text = callback.message.edit_text.call_args.args[0]
    assert "копировать не из чего" in text


# ---------------------------------------------------------------------------
# pick_copy_source_handler
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test__pick_copy_source_handler__own_source_copies_successfully(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fingerprint_access_service: FingerprintAccessService,
    fingerprint_management_service: FingerprintManagementService,
    fingerprint_resolution_service: FingerprintResolutionService,
    mock_admin_member: ChatMember,
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    user_id = 555
    source_values = FingerprintValues(
        user_agent="SourceUA", cpu_cores=4, device_memory=4, timezone=None, locale=None
    )

    async def _seed(session: AsyncSession) -> None:
        await fingerprint_management_service.set_own(
            session, source_chat_id, 0, values=source_values, created_by=user_id
        )

    source_chat_id = -100555
    await mock_db.write(_seed)

    target_chat_id = 555
    callback = make_mock_callback(
        data=f"fp:src:{source_chat_id}:0",
        chat_id=target_chat_id,
        user_id=user_id,
        chat_type="private",
    )
    # source_chat_id is a group -> ownership check needs is_group_admin via get_chat_member
    callback.bot.get_chat_member.return_value = mock_admin_member
    state = _state(target_chat_id, user_id)
    await state.set_state(FingerprintStates.selecting_copy_source)

    await pick_copy_source_handler(
        callback,
        state,
        mock_db,
        fingerprint_access_service,
        fingerprint_management_service,
        fingerprint_resolution_service,
    )

    assert await state.get_state() is None
    binding = await reload_fingerprint_binding(db_sessionmaker, target_chat_id)
    assert binding is not None
    assert binding["user_agent"] == "SourceUA"
    assert binding["cpu_cores"] == 4


@pytest.mark.unit
async def test__pick_copy_source_handler__foreign_source_is_denied(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fingerprint_access_service: FingerprintAccessService,
    fingerprint_management_service: FingerprintManagementService,
    fingerprint_resolution_service: FingerprintResolutionService,
    mock_regular_member: ChatMember,
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    foreign_chat_id = -100999

    async def _seed(session: AsyncSession) -> None:
        await fingerprint_management_service.set_own(
            session, foreign_chat_id, 0, values=EMPTY_VALUES, created_by=1
        )

    await mock_db.write(_seed)

    target_chat_id = 666
    callback = make_mock_callback(
        data=f"fp:src:{foreign_chat_id}:0",
        chat_id=target_chat_id,
        user_id=666,
        chat_type="private",
    )
    callback.bot.get_chat_member.return_value = mock_regular_member
    state = _state(target_chat_id, 666)
    await state.set_state(FingerprintStates.selecting_copy_source)

    await pick_copy_source_handler(
        callback,
        state,
        mock_db,
        fingerprint_access_service,
        fingerprint_management_service,
        fingerprint_resolution_service,
    )

    assert not await _binding_exists(db_sessionmaker, target_chat_id)


# ---------------------------------------------------------------------------
# reset_handler
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test__reset_handler__unbinds_and_cleans_up_orphan(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fingerprint_access_service: FingerprintAccessService,
    fingerprint_management_service: FingerprintManagementService,
    fingerprint_resolution_service: FingerprintResolutionService,
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    chat_id, user_id = 777, 777

    async def _seed(session: AsyncSession) -> None:
        await fingerprint_management_service.set_own(
            session, chat_id, 0, values=EMPTY_VALUES, created_by=user_id
        )

    await mock_db.write(_seed)
    assert await _binding_exists(db_sessionmaker, chat_id)

    callback = make_mock_callback(
        data="fp:reset", chat_id=chat_id, user_id=user_id, chat_type="private"
    )
    state = _state(chat_id, user_id)

    await reset_handler(
        callback,
        state,
        mock_db,
        fingerprint_access_service,
        fingerprint_management_service,
        fingerprint_resolution_service,
    )

    assert not await _binding_exists(db_sessionmaker, chat_id)


@pytest.mark.unit
async def test__reset_handler__no_binding_reports_already_default(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fingerprint_access_service: FingerprintAccessService,
    fingerprint_management_service: FingerprintManagementService,
    fingerprint_resolution_service: FingerprintResolutionService,
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    chat_id, user_id = 888, 888
    callback = make_mock_callback(
        data="fp:reset", chat_id=chat_id, user_id=user_id, chat_type="private"
    )
    state = _state(chat_id, user_id)

    await reset_handler(
        callback,
        state,
        mock_db,
        fingerprint_access_service,
        fingerprint_management_service,
        fingerprint_resolution_service,
    )

    text = callback.message.edit_text.call_args.args[0]
    assert "умолчанию" in text


@pytest.mark.unit
async def test__reset_handler__non_owner_is_denied(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fingerprint_access_service: FingerprintAccessService,
    fingerprint_management_service: FingerprintManagementService,
    fingerprint_resolution_service: FingerprintResolutionService,
    mock_regular_member: ChatMember,
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    chat_id = -100888

    async def _seed(session: AsyncSession) -> None:
        await fingerprint_management_service.set_own(
            session, chat_id, 0, values=EMPTY_VALUES, created_by=1
        )

    await mock_db.write(_seed)

    callback = make_mock_callback(
        data="fp:reset", chat_id=chat_id, user_id=999, chat_type="supergroup"
    )
    callback.bot.get_chat_member.return_value = mock_regular_member
    state = _state(chat_id, 999)

    await reset_handler(
        callback,
        state,
        mock_db,
        fingerprint_access_service,
        fingerprint_management_service,
        fingerprint_resolution_service,
    )

    assert await _binding_exists(db_sessionmaker, chat_id)
