"""Tests for the edit_shared terminal write: happy path, race-condition
rejection, and the fingerprint-deleted-mid-edit error surfaced to the user.
"""

from unittest.mock import AsyncMock, MagicMock

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
from core.exceptions import FingerprintNotFoundError
from core.fingerprint import FingerprintValues
from core.services.fingerprint_management_service import FingerprintManagementService
from core.services.fingerprint_resolution_service import FingerprintResolutionService
from tests.unit.conftest import (
    make_mock_callback,
    make_mock_database,
    make_mock_message,
    reload_fingerprint_binding,
)


def _state(chat_id: int, user_id: int, thread_id: int = 0) -> FSMContext:
    return FSMContext(
        storage=MemoryStorage(),
        key=StorageKey(bot_id=1, chat_id=chat_id, user_id=user_id, thread_id=thread_id),
    )


async def _drive_remaining_steps(
    *,
    step_texts: list[str],
    chat_id: int,
    user_id: int,
    state: FSMContext,
    mock_db,
    fingerprint_access_service,
    fingerprint_management_service,
    fingerprint_resolution_service,
    get_chat_member,
):
    """Send every step's answer except the last; return the final message."""
    messages = []
    for text in step_texts:
        message = make_mock_message(
            text=text, chat_id=chat_id, user_id=user_id, chat_type="supergroup"
        )
        message.bot.get_chat_member.side_effect = get_chat_member
        messages.append(message)
        await fingerprint_step_message_handler(
            message,
            state,
            mock_db,
            fingerprint_access_service,
            fingerprint_management_service,
            fingerprint_resolution_service,
        )
    return messages


@pytest.mark.unit
async def test__edit_shared_happy_path__applies_to_all_bound_sessions(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fingerprint_access_service: FingerprintAccessService,
    fingerprint_management_service: FingerprintManagementService,
    fingerprint_resolution_service: FingerprintResolutionService,
    mock_admin_member: ChatMember,
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    user_id = 11001
    chat_a, chat_b = -100111001, -100111002

    async def _seed(session: AsyncSession) -> int:
        fp_id = await fingerprint_management_service.set_own(
            session,
            chat_a,
            0,
            values=FingerprintValues(
                user_agent="OldUA",
                cpu_cores=4,
                device_memory=4,
                timezone="America/New_York",
                locale="en-US",
            ),
            created_by=user_id,
        )
        await fingerprint_management_service.copy_from(
            session, chat_b, 0, source_fingerprint_id=fp_id
        )
        return fp_id

    fingerprint_id = await mock_db.write(_seed)

    async def _get_chat_member(_chat_id: int, _uid: int) -> ChatMember:
        return mock_admin_member

    callback = make_mock_callback(
        data="fp:edit_shared", chat_id=chat_a, user_id=user_id, chat_type="supergroup"
    )
    callback.bot.get_chat_member.side_effect = _get_chat_member
    state = _state(chat_a, user_id)

    await start_edit_shared_handler(
        callback, mock_db, fingerprint_access_service, state
    )
    assert await state.get_state() == FingerprintStates.setting_user_agent.state

    await _drive_remaining_steps(
        step_texts=["Mozilla/5.0 SharedUA", "8", "2", "America/Chicago"],
        chat_id=chat_a,
        user_id=user_id,
        state=state,
        mock_db=mock_db,
        fingerprint_access_service=fingerprint_access_service,
        fingerprint_management_service=fingerprint_management_service,
        fingerprint_resolution_service=fingerprint_resolution_service,
        get_chat_member=_get_chat_member,
    )
    assert await state.get_state() == FingerprintStates.setting_locale.state

    final_message = make_mock_message(
        text="ru-RU", chat_id=chat_a, user_id=user_id, chat_type="supergroup"
    )
    final_message.bot.get_chat_member.side_effect = _get_chat_member
    await fingerprint_step_message_handler(
        final_message,
        state,
        mock_db,
        fingerprint_access_service,
        fingerprint_management_service,
        fingerprint_resolution_service,
    )

    assert await state.get_state() is None
    for chat_id in (chat_a, chat_b):
        binding = await reload_fingerprint_binding(db_sessionmaker, chat_id)
        assert binding is not None
        assert binding["fingerprint_id"] == fingerprint_id
        assert binding["user_agent"] == "Mozilla/5.0 SharedUA"
        assert binding["cpu_cores"] == 8
        assert binding["device_memory"] == 2
        assert binding["timezone"] == "America/Chicago"
        assert binding["locale"] == "ru-RU"


@pytest.mark.unit
async def test__edit_shared_terminal_write__session_rebound_away_mid_dialog_is_denied(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fingerprint_access_service: FingerprintAccessService,
    fingerprint_management_service: FingerprintManagementService,
    fingerprint_resolution_service: FingerprintResolutionService,
    mock_admin_member: ChatMember,
    mock_regular_member: ChatMember,
) -> None:
    """RED: TOCTOU race — the FSM's `fingerprint_id` goes stale mid-dialog.

    The user starts `edit_shared` eligibly (owns a session bound to F, which
    is shared by >=2 sessions). Before the terminal step, the user's own
    session is rebound away from F (e.g. lost via a rival "Set own" action).
    `is_owned` on the *current* chat still passes (still an admin there), but
    the user no longer owns any session bound to F — the terminal write must
    be rejected, not silently applied.
    """
    mock_db = make_mock_database(db_sessionmaker)
    user_id = 22002
    chat_a, chat_b = -100222001, -100222002

    async def _seed(session: AsyncSession) -> int:
        fp_id = await fingerprint_management_service.set_own(
            session,
            chat_a,
            0,
            values=FingerprintValues(
                user_agent="OriginalUA",
                cpu_cores=4,
                device_memory=4,
                timezone="America/New_York",
                locale="en-US",
            ),
            created_by=user_id,
        )
        await fingerprint_management_service.copy_from(
            session, chat_b, 0, source_fingerprint_id=fp_id
        )
        return fp_id

    fingerprint_id = await mock_db.write(_seed)

    async def _get_chat_member(chat_id: int, _uid: int) -> ChatMember:
        return mock_admin_member if chat_id == chat_a else mock_regular_member

    callback = make_mock_callback(
        data="fp:edit_shared", chat_id=chat_a, user_id=user_id, chat_type="supergroup"
    )
    callback.bot.get_chat_member.side_effect = _get_chat_member
    state = _state(chat_a, user_id)

    await start_edit_shared_handler(
        callback, mock_db, fingerprint_access_service, state
    )
    assert await state.get_state() == FingerprintStates.setting_user_agent.state

    # Race: chat_a is detached from F onto a brand-new fingerprint mid-dialog.
    # F now only has chat_b bound to it, which this user does not own.
    async def _rebind_away(session: AsyncSession) -> None:
        await fingerprint_management_service.set_own(
            session,
            chat_a,
            0,
            values=FingerprintValues(
                user_agent="Detached",
                cpu_cores=2,
                device_memory=2,
                timezone=None,
                locale=None,
            ),
            created_by=user_id,
        )

    await mock_db.write(_rebind_away)

    await _drive_remaining_steps(
        step_texts=["Mozilla/5.0 RaceUA", "8", "2", "America/Chicago"],
        chat_id=chat_a,
        user_id=user_id,
        state=state,
        mock_db=mock_db,
        fingerprint_access_service=fingerprint_access_service,
        fingerprint_management_service=fingerprint_management_service,
        fingerprint_resolution_service=fingerprint_resolution_service,
        get_chat_member=_get_chat_member,
    )
    assert await state.get_state() == FingerprintStates.setting_locale.state

    final_message = make_mock_message(
        text="ru-RU", chat_id=chat_a, user_id=user_id, chat_type="supergroup"
    )
    final_message.bot.get_chat_member.side_effect = _get_chat_member
    await fingerprint_step_message_handler(
        final_message,
        state,
        mock_db,
        fingerprint_access_service,
        fingerprint_management_service,
        fingerprint_resolution_service,
    )

    assert await state.get_state() is None
    reply_text = final_message.reply.call_args.args[0]
    assert "Недостаточно прав" in reply_text

    binding_b = await reload_fingerprint_binding(db_sessionmaker, chat_b)
    assert binding_b is not None
    assert binding_b["fingerprint_id"] == fingerprint_id
    assert binding_b["user_agent"] == "OriginalUA"
    assert binding_b["cpu_cores"] == 4
    assert binding_b["device_memory"] == 4
    assert binding_b["timezone"] == "America/New_York"
    assert binding_b["locale"] == "en-US"


@pytest.mark.unit
async def test__edit_shared_terminal_write__fingerprint_deleted_shows_already_deleted_message(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fingerprint_access_service: FingerprintAccessService,
    fingerprint_management_service: FingerprintManagementService,
    fingerprint_resolution_service: FingerprintResolutionService,
    mock_admin_member: ChatMember,
) -> None:
    """The terminal write can still race with the fingerprint being deleted;
    `edit_shared` raises `FingerprintNotFoundError` and the handler must
    surface the "already deleted" message and clear the FSM state."""
    mock_db = make_mock_database(db_sessionmaker)
    user_id = 33003
    chat_a, chat_b = -100333001, -100333002

    async def _seed(session: AsyncSession) -> int:
        fp_id = await fingerprint_management_service.set_own(
            session,
            chat_a,
            0,
            values=FingerprintValues(
                user_agent="OldUA",
                cpu_cores=4,
                device_memory=4,
                timezone="America/New_York",
                locale="en-US",
            ),
            created_by=user_id,
        )
        await fingerprint_management_service.copy_from(
            session, chat_b, 0, source_fingerprint_id=fp_id
        )
        return fp_id

    fingerprint_id = await mock_db.write(_seed)

    async def _get_chat_member(_chat_id: int, _uid: int) -> ChatMember:
        return mock_admin_member

    callback = make_mock_callback(
        data="fp:edit_shared", chat_id=chat_a, user_id=user_id, chat_type="supergroup"
    )
    callback.bot.get_chat_member.side_effect = _get_chat_member
    state = _state(chat_a, user_id)

    await start_edit_shared_handler(
        callback, mock_db, fingerprint_access_service, state
    )
    assert await state.get_state() == FingerprintStates.setting_user_agent.state

    failing_management_service = MagicMock(spec=FingerprintManagementService)
    failing_management_service.edit_shared = AsyncMock(
        side_effect=FingerprintNotFoundError(f"Fingerprint {fingerprint_id} not found")
    )

    await _drive_remaining_steps(
        step_texts=["Mozilla/5.0 UA", "8", "2", "America/Chicago"],
        chat_id=chat_a,
        user_id=user_id,
        state=state,
        mock_db=mock_db,
        fingerprint_access_service=fingerprint_access_service,
        fingerprint_management_service=failing_management_service,
        fingerprint_resolution_service=fingerprint_resolution_service,
        get_chat_member=_get_chat_member,
    )
    assert await state.get_state() == FingerprintStates.setting_locale.state

    final_message = make_mock_message(
        text="ru-RU", chat_id=chat_a, user_id=user_id, chat_type="supergroup"
    )
    final_message.bot.get_chat_member.side_effect = _get_chat_member
    await fingerprint_step_message_handler(
        final_message,
        state,
        mock_db,
        fingerprint_access_service,
        failing_management_service,
        fingerprint_resolution_service,
    )

    assert await state.get_state() is None
    reply_text = final_message.reply.call_args.args[0]
    assert "уже был удалён" in reply_text
