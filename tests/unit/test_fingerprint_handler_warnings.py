"""Tests for the two mandatory warnings (ARCH section on FSM warnings):

1. Editing a shared fingerprint warns how many sessions it affects.
2. Changing an already-authenticated session's fingerprint warns about a
   possible fresh Cloudflare check / logout.
"""

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ChatMember
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.handlers.fingerprint import (
    fingerprint_step_message_handler,
    start_edit_shared_handler,
)
from bot.services.fingerprint_access_service import FingerprintAccessService
from bot.states.fingerprint import FingerprintStates
from core.db.repositories.chat_session_repository import ChatSessionRepository
from core.fingerprint import FingerprintValues
from core.services.fingerprint_management_service import FingerprintManagementService
from core.services.fingerprint_resolution_service import FingerprintResolutionService
from tests.unit.conftest import (
    make_mock_callback,
    make_mock_database,
    make_mock_message,
)

EMPTY_VALUES = FingerprintValues(
    user_agent=None, cpu_cores=None, device_memory=None, timezone=None, locale=None
)


def _state(chat_id: int, user_id: int, thread_id: int = 0) -> FSMContext:
    return FSMContext(
        storage=MemoryStorage(),
        key=StorageKey(bot_id=1, chat_id=chat_id, user_id=user_id, thread_id=thread_id),
    )


@pytest.mark.unit
async def test__edit_shared__warns_how_many_sessions_are_affected(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fingerprint_access_service: FingerprintAccessService,
    fingerprint_management_service: FingerprintManagementService,
    mock_admin_member: ChatMember,
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    user_id = 111
    chat_a, chat_b = -100111, -100222

    async def _seed(session: AsyncSession) -> None:
        fp_id = await fingerprint_management_service.set_own(
            session, chat_a, 0, values=EMPTY_VALUES, created_by=user_id
        )
        await fingerprint_management_service.copy_from(
            session, chat_b, 0, source_fingerprint_id=fp_id
        )

    await mock_db.write(_seed)

    callback = make_mock_callback(
        data="fp:edit_shared", chat_id=chat_a, user_id=user_id, chat_type="supergroup"
    )
    callback.bot.get_chat_member.return_value = mock_admin_member
    state = _state(chat_a, user_id)

    await start_edit_shared_handler(
        callback, mock_db, fingerprint_access_service, state
    )

    assert await state.get_state() == FingerprintStates.setting_user_agent.state
    text = callback.message.edit_text.call_args.args[0]
    assert "затронет 2" in text


@pytest.mark.unit
async def test__edit_shared__not_offered_when_only_one_session_bound(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fingerprint_access_service: FingerprintAccessService,
    fingerprint_management_service: FingerprintManagementService,
    mock_admin_member: ChatMember,
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    user_id, chat_id = 222, -100333

    async def _seed(session: AsyncSession) -> None:
        await fingerprint_management_service.set_own(
            session, chat_id, 0, values=EMPTY_VALUES, created_by=user_id
        )

    await mock_db.write(_seed)

    callback = make_mock_callback(
        data="fp:edit_shared", chat_id=chat_id, user_id=user_id, chat_type="supergroup"
    )
    callback.bot.get_chat_member.return_value = mock_admin_member
    state = _state(chat_id, user_id)

    await start_edit_shared_handler(
        callback, mock_db, fingerprint_access_service, state
    )

    assert await state.get_state() is None
    callback.answer.assert_called_once()
    assert callback.answer.call_args.kwargs.get("show_alert") is True


@pytest.mark.unit
async def test__already_authenticated_session__warns_about_cloudflare_recheck(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fingerprint_access_service: FingerprintAccessService,
    fingerprint_management_service: FingerprintManagementService,
    fingerprint_resolution_service: FingerprintResolutionService,
) -> None:
    from bot.handlers.fingerprint import start_set_own_handler

    mock_db = make_mock_database(db_sessionmaker)
    chat_id, user_id = 9001, 9001

    async def _seed(session: AsyncSession) -> None:
        await ChatSessionRepository(session).create(
            chat_id=chat_id,
            email="user@example.com",
            session_path="/data/sessions/9001",
        )

    await mock_db.write(_seed)

    state = _state(chat_id, user_id)
    start_callback = make_mock_callback(
        data="fp:set_own", chat_id=chat_id, user_id=user_id, chat_type="private"
    )
    await start_set_own_handler(
        start_callback, mock_db, fingerprint_access_service, state
    )

    for text in ["UA", "8", "8", "America/New_York"]:
        message = make_mock_message(
            text=text, chat_id=chat_id, user_id=user_id, chat_type="private"
        )
        await fingerprint_step_message_handler(
            message,
            state,
            mock_db,
            fingerprint_access_service,
            fingerprint_management_service,
            fingerprint_resolution_service,
        )

    final_message = make_mock_message(
        text="en-US", chat_id=chat_id, user_id=user_id, chat_type="private"
    )
    await fingerprint_step_message_handler(
        final_message,
        state,
        mock_db,
        fingerprint_access_service,
        fingerprint_management_service,
        fingerprint_resolution_service,
    )

    final_text = final_message.reply.call_args.args[0]
    assert "Cloudflare" in final_text


@pytest.mark.unit
async def test__no_existing_session__no_cloudflare_warning(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fingerprint_access_service: FingerprintAccessService,
    fingerprint_management_service: FingerprintManagementService,
    fingerprint_resolution_service: FingerprintResolutionService,
) -> None:
    from bot.handlers.fingerprint import start_set_own_handler

    mock_db = make_mock_database(db_sessionmaker)
    chat_id, user_id = 9002, 9002
    state = _state(chat_id, user_id)

    start_callback = make_mock_callback(
        data="fp:set_own", chat_id=chat_id, user_id=user_id, chat_type="private"
    )
    await start_set_own_handler(
        start_callback, mock_db, fingerprint_access_service, state
    )

    for text in ["UA", "8", "8", "America/New_York"]:
        message = make_mock_message(
            text=text, chat_id=chat_id, user_id=user_id, chat_type="private"
        )
        await fingerprint_step_message_handler(
            message,
            state,
            mock_db,
            fingerprint_access_service,
            fingerprint_management_service,
            fingerprint_resolution_service,
        )

    final_message = make_mock_message(
        text="en-US", chat_id=chat_id, user_id=user_id, chat_type="private"
    )
    await fingerprint_step_message_handler(
        final_message,
        state,
        mock_db,
        fingerprint_access_service,
        fingerprint_management_service,
        fingerprint_resolution_service,
    )

    final_text = final_message.reply.call_args.args[0]
    assert "Cloudflare" not in final_text
