"""Tests for the set-own 5-step dialog: happy path, skip, repeat-on-error."""

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.handlers.fingerprint import (
    fingerprint_step_message_handler,
    start_set_own_handler,
)
from bot.services.fingerprint_access_service import FingerprintAccessService
from bot.states.fingerprint import FingerprintStates
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


@pytest.mark.unit
async def test__set_own_happy_path__creates_binding_with_entered_values(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fingerprint_access_service: FingerprintAccessService,
    fingerprint_management_service: FingerprintManagementService,
    fingerprint_resolution_service: FingerprintResolutionService,
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    chat_id, user_id = 1001, 1001
    state = _state(chat_id, user_id)

    start_callback = make_mock_callback(
        data="fp:set_own", chat_id=chat_id, user_id=user_id, chat_type="private"
    )
    await start_set_own_handler(
        start_callback, mock_db, fingerprint_access_service, state
    )

    assert await state.get_state() == FingerprintStates.setting_user_agent.state
    prompt = start_callback.message.edit_text.call_args.args[0]
    assert "User-Agent" in prompt

    steps = [
        ("Mozilla/5.0 TestAgent", FingerprintStates.setting_cpu_cores.state),
        ("8", FingerprintStates.setting_device_memory.state),
        ("4", FingerprintStates.setting_timezone.state),
        ("America/New_York", FingerprintStates.setting_locale.state),
    ]
    for text, expected_next_state in steps:
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
        assert await state.get_state() == expected_next_state

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

    assert await state.get_state() is None
    final_reply = final_message.reply.call_args.args[0]
    assert "Mozilla/5.0 TestAgent" in final_reply

    binding = await reload_fingerprint_binding(db_sessionmaker, chat_id)
    assert binding is not None
    assert binding["user_agent"] == "Mozilla/5.0 TestAgent"
    assert binding["cpu_cores"] == 8
    assert binding["device_memory"] == 4
    assert binding["timezone"] == "America/New_York"
    assert binding["locale"] == "en-US"


@pytest.mark.unit
async def test__set_own_skip__keeps_seeded_value_from_current_binding(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fingerprint_access_service: FingerprintAccessService,
    fingerprint_management_service: FingerprintManagementService,
    fingerprint_resolution_service: FingerprintResolutionService,
) -> None:
    from bot.handlers.fingerprint import skip_step_handler

    mock_db = make_mock_database(db_sessionmaker)
    chat_id, user_id = 2002, 2002

    async def _seed(session: AsyncSession) -> None:
        await fingerprint_management_service.set_own(
            session,
            chat_id,
            0,
            values=FingerprintValues(
                user_agent="OldUA",
                cpu_cores=8,
                device_memory=8,
                timezone="America/New_York",
                locale="en-US",
            ),
            created_by=user_id,
        )

    await mock_db.write(_seed)

    state = _state(chat_id, user_id)
    start_callback = make_mock_callback(
        data="fp:set_own", chat_id=chat_id, user_id=user_id, chat_type="private"
    )
    await start_set_own_handler(
        start_callback, mock_db, fingerprint_access_service, state
    )

    skip_callback = make_mock_callback(
        data="fp:skip", chat_id=chat_id, user_id=user_id, chat_type="private"
    )
    await skip_step_handler(
        skip_callback,
        state,
        mock_db,
        fingerprint_access_service,
        fingerprint_management_service,
        fingerprint_resolution_service,
    )
    assert await state.get_state() == FingerprintStates.setting_cpu_cores.state

    cores_message = make_mock_message(
        text="16", chat_id=chat_id, user_id=user_id, chat_type="private"
    )
    await fingerprint_step_message_handler(
        cores_message,
        state,
        mock_db,
        fingerprint_access_service,
        fingerprint_management_service,
        fingerprint_resolution_service,
    )

    for _ in range(3):  # skip memory, timezone, locale (terminal write)
        skip_callback = make_mock_callback(
            data="fp:skip", chat_id=chat_id, user_id=user_id, chat_type="private"
        )
        await skip_step_handler(
            skip_callback,
            state,
            mock_db,
            fingerprint_access_service,
            fingerprint_management_service,
            fingerprint_resolution_service,
        )

    assert await state.get_state() is None
    binding = await reload_fingerprint_binding(db_sessionmaker, chat_id)
    assert binding is not None
    assert binding["user_agent"] == "OldUA"  # kept via skip
    assert binding["cpu_cores"] == 16  # overridden
    assert binding["device_memory"] == 8  # kept via skip
    assert binding["timezone"] == "America/New_York"  # kept via skip
    assert binding["locale"] == "en-US"  # kept via skip


@pytest.mark.unit
async def test__set_own__invalid_number_reasks_with_not_a_number_hint(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fingerprint_access_service: FingerprintAccessService,
    fingerprint_management_service: FingerprintManagementService,
    fingerprint_resolution_service: FingerprintResolutionService,
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    chat_id, user_id = 3003, 3003
    state = _state(chat_id, user_id)

    start_callback = make_mock_callback(
        data="fp:set_own", chat_id=chat_id, user_id=user_id, chat_type="private"
    )
    await start_set_own_handler(
        start_callback, mock_db, fingerprint_access_service, state
    )

    ua_message = make_mock_message(
        text="Mozilla/5.0", chat_id=chat_id, user_id=user_id, chat_type="private"
    )
    await fingerprint_step_message_handler(
        ua_message,
        state,
        mock_db,
        fingerprint_access_service,
        fingerprint_management_service,
        fingerprint_resolution_service,
    )
    assert await state.get_state() == FingerprintStates.setting_cpu_cores.state

    bad_cores_message = make_mock_message(
        text="not-a-number", chat_id=chat_id, user_id=user_id, chat_type="private"
    )
    await fingerprint_step_message_handler(
        bad_cores_message,
        state,
        mock_db,
        fingerprint_access_service,
        fingerprint_management_service,
        fingerprint_resolution_service,
    )

    assert await state.get_state() == FingerprintStates.setting_cpu_cores.state
    reply_text = bad_cores_message.reply.call_args.args[0]
    assert "число" in reply_text


@pytest.mark.unit
async def test__set_own__out_of_range_cores_reasks_with_validator_message(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fingerprint_access_service: FingerprintAccessService,
    fingerprint_management_service: FingerprintManagementService,
    fingerprint_resolution_service: FingerprintResolutionService,
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    chat_id, user_id = 4004, 4004
    state = _state(chat_id, user_id)

    start_callback = make_mock_callback(
        data="fp:set_own", chat_id=chat_id, user_id=user_id, chat_type="private"
    )
    await start_set_own_handler(
        start_callback, mock_db, fingerprint_access_service, state
    )

    ua_message = make_mock_message(
        text="Mozilla/5.0", chat_id=chat_id, user_id=user_id, chat_type="private"
    )
    await fingerprint_step_message_handler(
        ua_message,
        state,
        mock_db,
        fingerprint_access_service,
        fingerprint_management_service,
        fingerprint_resolution_service,
    )

    bad_cores_message = make_mock_message(
        text="999", chat_id=chat_id, user_id=user_id, chat_type="private"
    )
    await fingerprint_step_message_handler(
        bad_cores_message,
        state,
        mock_db,
        fingerprint_access_service,
        fingerprint_management_service,
        fingerprint_resolution_service,
    )

    assert await state.get_state() == FingerprintStates.setting_cpu_cores.state
    reply_text = bad_cores_message.reply.call_args.args[0]
    assert "between 1 and 32" in reply_text

    good_cores_message = make_mock_message(
        text="8", chat_id=chat_id, user_id=user_id, chat_type="private"
    )
    await fingerprint_step_message_handler(
        good_cores_message,
        state,
        mock_db,
        fingerprint_access_service,
        fingerprint_management_service,
        fingerprint_resolution_service,
    )
    assert await state.get_state() == FingerprintStates.setting_device_memory.state


@pytest.mark.unit
async def test__set_own__invalid_device_memory_reasks_with_validator_message(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fingerprint_access_service: FingerprintAccessService,
    fingerprint_management_service: FingerprintManagementService,
    fingerprint_resolution_service: FingerprintResolutionService,
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    chat_id, user_id = 5005, 5005
    state = _state(chat_id, user_id)
    await state.set_state(FingerprintStates.setting_device_memory)
    await state.update_data(
        mode="set_own",
        draft={
            "user_agent": "UA",
            "cpu_cores": 8,
            "device_memory": None,
            "timezone": None,
            "locale": None,
        },
    )

    bad_memory_message = make_mock_message(
        text="3", chat_id=chat_id, user_id=user_id, chat_type="private"
    )
    await fingerprint_step_message_handler(
        bad_memory_message,
        state,
        mock_db,
        fingerprint_access_service,
        fingerprint_management_service,
        fingerprint_resolution_service,
    )

    assert await state.get_state() == FingerprintStates.setting_device_memory.state
    reply_text = bad_memory_message.reply.call_args.args[0]
    assert "must be one of" in reply_text
