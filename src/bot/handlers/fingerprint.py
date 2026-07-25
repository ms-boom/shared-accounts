"""Handlers for the `/fingerprint` command — view card + FSM dialog.

Thin presentation layer: business rules (merge, ownership, orphan cleanup)
live in `core.services.fingerprint_resolution_service` /
`fingerprint_management_service` and `bot.services.fingerprint_access_service`.
This module only renders prompts/keyboards and routes FSM steps to those
services.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.fingerprint_access_service import FingerprintAccessService
from bot.states.fingerprint import FingerprintStates
from core.db.database import Database
from core.db.repositories.chat_session_repository import ChatSessionRepository
from core.db.repositories.fingerprint_repository import FingerprintRepository
from core.db.repositories.session_fingerprint_repository import (
    SessionFingerprintRepository,
)
from core.exceptions import FingerprintNotFoundError
from core.fingerprint import (
    FingerprintValues,
    FingerprintView,
    build_label,
    validate_cpu_cores,
    validate_device_memory,
    validate_locale,
    validate_timezone,
    validate_user_agent,
)
from core.services.fingerprint_management_service import FingerprintManagementService
from core.services.fingerprint_resolution_service import FingerprintResolutionService

logger = logging.getLogger(__name__)

router = Router(name="fingerprint")

_NOT_ADMIN_TEXT = (
    "❌ Только администраторы группы могут управлять отпечатком браузера сессии."
)
_CLOUDFLARE_WARNING = (
    "⚠️ Сессия уже авторизована — изменение отпечатка может вызвать повторную "
    "проверку Cloudflare или разлогинить сессию."
)
_NOTHING_TO_COPY_TEXT = (
    "У вас нет других сессий с отпечатком — копировать не из чего.\n\n"
    "Используйте «Задать свой», чтобы создать новый, или оставьте профиль по умолчанию."
)

_FIELD_TITLES = {
    "user_agent": "User-Agent",
    "cpu_cores": "CPU cores",
    "device_memory": "Device memory",
    "timezone": "Timezone",
    "locale": "Locale",
}


def _thread_id(message: Message) -> int:
    """Extract thread_id from a message (0 for main chat, >0 for topics)."""
    return message.message_thread_id if message.message_thread_id else 0


# ---------------------------------------------------------------------------
# 5-step chain metadata
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Step:
    field: str
    state: State
    next_state: State | None
    prompt: str
    is_int: bool


_STEPS: list[_Step] = [
    _Step(
        "user_agent",
        FingerprintStates.setting_user_agent,
        FingerprintStates.setting_cpu_cores,
        "Введите User-Agent (например, Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36):",
        is_int=False,
    ),
    _Step(
        "cpu_cores",
        FingerprintStates.setting_cpu_cores,
        FingerprintStates.setting_device_memory,
        "Введите число ядер CPU (1-32):",
        is_int=True,
    ),
    _Step(
        "device_memory",
        FingerprintStates.setting_device_memory,
        FingerprintStates.setting_timezone,
        "Введите объём памяти в ГБ (1, 2, 4 или 8):",
        is_int=True,
    ),
    _Step(
        "timezone",
        FingerprintStates.setting_timezone,
        FingerprintStates.setting_locale,
        "Введите IANA таймзону (например, America/New_York):",
        is_int=False,
    ),
    _Step(
        "locale",
        FingerprintStates.setting_locale,
        None,
        "Введите локаль (например, en-US):",
        is_int=False,
    ),
]
_STEP_BY_STATE = {step.state.state: step for step in _STEPS}
_ALL_STEP_STATES = [step.state for step in _STEPS]

_VALIDATORS: dict[str, Callable[[Any], Any]] = {
    "user_agent": validate_user_agent,
    "cpu_cores": validate_cpu_cores,
    "device_memory": validate_device_memory,
    "timezone": validate_timezone,
    "locale": validate_locale,
}


def _values_to_dict(values: FingerprintValues | None) -> dict:
    """Convert a `FingerprintValues` into a JSON-serializable dict for FSM data."""
    if values is None:
        values = FingerprintValues(
            user_agent=None,
            cpu_cores=None,
            device_memory=None,
            timezone=None,
            locale=None,
        )
    return {
        "user_agent": values.user_agent,
        "cpu_cores": values.cpu_cores,
        "device_memory": values.device_memory,
        "timezone": values.timezone,
        "locale": values.locale,
    }


def _dict_to_values(draft: dict) -> FingerprintValues:
    return FingerprintValues(
        user_agent=draft.get("user_agent"),
        cpu_cores=draft.get("cpu_cores"),
        device_memory=draft.get("device_memory"),
        timezone=draft.get("timezone"),
        locale=draft.get("locale"),
    )


# ---------------------------------------------------------------------------
# View card + keyboards
# ---------------------------------------------------------------------------


def _format_view_card(view: FingerprintView) -> str:
    lines = ["🖥 <b>Отпечаток браузера этой сессии</b>", ""]
    for field, title in _FIELD_TITLES.items():
        value = getattr(view.effective, field)
        source_label = "свой" if view.source[field] == "own" else "по умолчанию"
        lines.append(f"• {title}: <code>{value}</code> ({source_label})")
    if view.label:
        lines.append("")
        lines.append(f"Метка: {view.label}")
    if view.shared_session_count > 1:
        lines.append("")
        lines.append(
            f"🔗 Используется в {view.shared_session_count} сессиях (включая эту)."
        )
    return "\n".join(lines)


def _build_menu_keyboard(
    *, can_edit_shared: bool, can_reset: bool, shared_count: int
) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="🆕 Задать свой", callback_data="fp:set_own")]]
    if can_edit_shared:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"✏️ Изменить для всех ({shared_count})",
                    callback_data="fp:edit_shared",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="📋 Скопировать из своей сессии", callback_data="fp:copy"
            )
        ]
    )
    if can_reset:
        rows.append([InlineKeyboardButton(text="♻️ Сбросить", callback_data="fp:reset")])
    rows.append([InlineKeyboardButton(text="Отмена", callback_data="fp:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _step_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data="fp:skip")],
            [InlineKeyboardButton(text="Отмена", callback_data="fp:cancel")],
        ]
    )


def _cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Отмена", callback_data="fp:cancel")]
        ]
    )


def _copy_source_keyboard(sources: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for source in sources:
        label = source["label"] or f"{source['chat_id']}/{source['thread_id']}"
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"fp:src:{source['chat_id']}:{source['thread_id']}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="Отмена", callback_data="fp:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------------------------------------------------------
# /fingerprint command — MENU
# ---------------------------------------------------------------------------


@router.message(Command("fingerprint"))
async def fingerprint_handler(
    message: Message,
    database: Database,
    fingerprint_resolution_service: FingerprintResolutionService,
    fingerprint_access_service: FingerprintAccessService,
    state: FSMContext,
) -> None:
    """Show the fingerprint view card + management menu for this session."""
    if not message.bot or not message.from_user:
        await message.reply("❌ Не удалось определить пользователя.")
        return

    chat_id = message.chat.id
    thread_id = _thread_id(message)
    user_id = message.from_user.id

    owned = await fingerprint_access_service.is_owned(
        message.bot, user_id, chat_id, thread_id
    )
    if not owned:
        await message.reply(_NOT_ADMIN_TEXT)
        return

    await state.clear()

    async with database.read() as session:
        view = await fingerprint_resolution_service.resolve_view(
            session, chat_id, thread_id
        )
        binding = await SessionFingerprintRepository(session).get(chat_id, thread_id)
        can_edit_shared = False
        if binding is not None and view.shared_session_count > 1:
            can_edit_shared = await fingerprint_access_service.can_edit_fingerprint(
                session, message.bot, user_id, binding["fingerprint_id"]
            )

    text = _format_view_card(view)
    keyboard = _build_menu_keyboard(
        can_edit_shared=can_edit_shared,
        can_reset=binding is not None,
        shared_count=view.shared_session_count,
    )
    await message.reply(text, reply_markup=keyboard, parse_mode="HTML")


# ---------------------------------------------------------------------------
# Start set-own / edit-shared
# ---------------------------------------------------------------------------


@router.callback_query(F.data == "fp:set_own")
async def start_set_own_handler(
    callback: CallbackQuery,
    database: Database,
    fingerprint_access_service: FingerprintAccessService,
    state: FSMContext,
) -> None:
    """Enter the 5-step chain to create a fresh, session-only fingerprint."""
    if not isinstance(callback.message, Message) or not callback.bot:
        await callback.answer()
        return

    chat_id = callback.message.chat.id
    thread_id = _thread_id(callback.message)
    user_id = callback.from_user.id

    owned = await fingerprint_access_service.is_owned(
        callback.bot, user_id, chat_id, thread_id
    )
    if not owned:
        await callback.answer("❌ Недостаточно прав.", show_alert=True)
        return

    async with database.read() as session:
        binding = await SessionFingerprintRepository(session).get(chat_id, thread_id)
        current_values = None
        if binding is not None:
            current_values = await FingerprintRepository(session).get_values(
                binding["fingerprint_id"]
            )

    await state.set_data({"mode": "set_own", "draft": _values_to_dict(current_values)})
    await state.set_state(FingerprintStates.setting_user_agent)

    first_step = _STEP_BY_STATE[FingerprintStates.setting_user_agent.state]
    await callback.message.edit_text(first_step.prompt, reply_markup=_step_keyboard())
    await callback.answer()


@router.callback_query(F.data == "fp:edit_shared")
async def start_edit_shared_handler(
    callback: CallbackQuery,
    database: Database,
    fingerprint_access_service: FingerprintAccessService,
    state: FSMContext,
) -> None:
    """Enter the 5-step chain to edit a fingerprint shared by several sessions."""
    if not isinstance(callback.message, Message) or not callback.bot:
        await callback.answer()
        return

    chat_id = callback.message.chat.id
    thread_id = _thread_id(callback.message)
    user_id = callback.from_user.id

    owned = await fingerprint_access_service.is_owned(
        callback.bot, user_id, chat_id, thread_id
    )
    if not owned:
        await callback.answer("❌ Недостаточно прав.", show_alert=True)
        return

    async with database.read() as session:
        binding = await SessionFingerprintRepository(session).get(chat_id, thread_id)
        if binding is None:
            await callback.answer("❌ Отпечаток не найден.", show_alert=True)
            return

        fingerprint_id = binding["fingerprint_id"]
        shared_count = await SessionFingerprintRepository(
            session
        ).count_for_fingerprint(fingerprint_id)
        can_edit = await fingerprint_access_service.can_edit_fingerprint(
            session, callback.bot, user_id, fingerprint_id
        )
        current_values = await FingerprintRepository(session).get_values(fingerprint_id)

    if shared_count <= 1 or not can_edit:
        await callback.answer(
            "❌ Недостаточно прав для правки общего отпечатка.", show_alert=True
        )
        return

    await state.set_data(
        {
            "mode": "edit_shared",
            "fingerprint_id": fingerprint_id,
            "draft": _values_to_dict(current_values),
        }
    )
    await state.set_state(FingerprintStates.setting_user_agent)

    first_step = _STEP_BY_STATE[FingerprintStates.setting_user_agent.state]
    warning = f"⚠️ Правка затронет {shared_count} сессий.\n\n"
    await callback.message.edit_text(
        warning + first_step.prompt, reply_markup=_step_keyboard()
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Shared step-advance logic (message text + skip callback both route here)
# ---------------------------------------------------------------------------


async def _apply_step_and_continue(
    state: FSMContext,
    step: _Step,
    new_value: object | None,
    *,
    chat_id: int,
    thread_id: int,
    user_id: int,
    bot: Bot,
    database: Database,
    fingerprint_access_service: FingerprintAccessService,
    fingerprint_management_service: FingerprintManagementService,
    fingerprint_resolution_service: FingerprintResolutionService,
) -> tuple[str, InlineKeyboardMarkup | None]:
    """Advance the FSM one step, or perform the terminal write on the last step.

    Returns the text and optional keyboard to show the user next.
    """
    data = await state.get_data()
    draft = dict(data.get("draft", {}))
    if new_value is not None:
        draft[step.field] = new_value

    if step.next_state is not None:
        await state.update_data(draft=draft)
        await state.set_state(step.next_state)
        next_step = _STEP_BY_STATE[step.next_state.state]
        return next_step.prompt, _step_keyboard()

    # Terminal step (locale) — re-check ownership immediately before the write.
    owned = await fingerprint_access_service.is_owned(bot, user_id, chat_id, thread_id)
    if not owned:
        await state.clear()
        return "❌ Недостаточно прав для завершения изменения.", None

    values = _dict_to_values(draft)
    mode = data["mode"]

    if mode == "edit_shared":
        fingerprint_id = data["fingerprint_id"]
        async with database.read() as session:
            can_edit = await fingerprint_access_service.can_edit_fingerprint(
                session, bot, user_id, fingerprint_id
            )
        if not can_edit:
            await state.clear()
            return "❌ Недостаточно прав для завершения изменения.", None

    try:
        if mode == "set_own":

            async def _write_set_own(session: AsyncSession) -> int:
                return await fingerprint_management_service.set_own(
                    session, chat_id, thread_id, values=values, created_by=user_id
                )

            await database.write(_write_set_own)
        else:
            label = build_label(values)

            async def _write_edit_shared(session: AsyncSession) -> None:
                await fingerprint_management_service.edit_shared(
                    session, fingerprint_id, values=values, label=label
                )

            await database.write(_write_edit_shared)
    except FingerprintNotFoundError:
        await state.clear()
        return "❌ Этот отпечаток уже был удалён — изменения не сохранены.", None

    text = await _render_result_card(
        database, fingerprint_resolution_service, chat_id, thread_id
    )
    await state.clear()
    return text, None


async def _render_result_card(
    database: Database,
    fingerprint_resolution_service: FingerprintResolutionService,
    chat_id: int,
    thread_id: int,
    *,
    extra_note: str | None = None,
) -> str:
    """Build the post-write confirmation card, including the Cloudflare warning."""
    async with database.read() as session:
        already_authenticated = (
            await ChatSessionRepository(session).get_by_chat_id(chat_id, thread_id)
        ) is not None
        view = await fingerprint_resolution_service.resolve_view(
            session, chat_id, thread_id
        )

    text = _format_view_card(view)
    if extra_note:
        text = f"{extra_note}\n\n{text}"
    if already_authenticated:
        text = f"{text}\n\n{_CLOUDFLARE_WARNING}"
    return text


@router.message(StateFilter(*_ALL_STEP_STATES))
async def fingerprint_step_message_handler(
    message: Message,
    state: FSMContext,
    database: Database,
    fingerprint_access_service: FingerprintAccessService,
    fingerprint_management_service: FingerprintManagementService,
    fingerprint_resolution_service: FingerprintResolutionService,
) -> None:
    """Handle a typed answer for the current step of the 5-step chain."""
    if not message.text or not message.from_user or not message.bot:
        await message.reply("❌ Ожидался текстовый ответ.")
        return

    current_state = await state.get_state()
    step = _STEP_BY_STATE[current_state]
    raw = message.text.strip()

    if step.is_int:
        try:
            candidate: object = int(raw)
        except ValueError:
            await message.reply(
                f"❌ Введите число.\n\n{step.prompt}", reply_markup=_step_keyboard()
            )
            return
    else:
        candidate = raw

    try:
        validated = _VALIDATORS[step.field](candidate)
    except ValueError as e:
        await message.reply(f"❌ {e}\n\n{step.prompt}", reply_markup=_step_keyboard())
        return

    text, keyboard = await _apply_step_and_continue(
        state,
        step,
        validated,
        chat_id=message.chat.id,
        thread_id=_thread_id(message),
        user_id=message.from_user.id,
        bot=message.bot,
        database=database,
        fingerprint_access_service=fingerprint_access_service,
        fingerprint_management_service=fingerprint_management_service,
        fingerprint_resolution_service=fingerprint_resolution_service,
    )
    await message.reply(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "fp:skip", StateFilter(*_ALL_STEP_STATES))
async def skip_step_handler(
    callback: CallbackQuery,
    state: FSMContext,
    database: Database,
    fingerprint_access_service: FingerprintAccessService,
    fingerprint_management_service: FingerprintManagementService,
    fingerprint_resolution_service: FingerprintResolutionService,
) -> None:
    """Skip the current step — the draft keeps whatever it was seeded with."""
    if not isinstance(callback.message, Message) or not callback.bot:
        await callback.answer()
        return

    current_state = await state.get_state()
    step = _STEP_BY_STATE[current_state]

    text, keyboard = await _apply_step_and_continue(
        state,
        step,
        None,
        chat_id=callback.message.chat.id,
        thread_id=_thread_id(callback.message),
        user_id=callback.from_user.id,
        bot=callback.bot,
        database=database,
        fingerprint_access_service=fingerprint_access_service,
        fingerprint_management_service=fingerprint_management_service,
        fingerprint_resolution_service=fingerprint_resolution_service,
    )
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


# ---------------------------------------------------------------------------
# Copy from my session
# ---------------------------------------------------------------------------


@router.callback_query(F.data == "fp:copy")
async def start_copy_handler(
    callback: CallbackQuery,
    database: Database,
    fingerprint_access_service: FingerprintAccessService,
    state: FSMContext,
) -> None:
    """Show the picker of sessions the user owns to copy a fingerprint from."""
    if not isinstance(callback.message, Message) or not callback.bot:
        await callback.answer()
        return

    user_id = callback.from_user.id

    async with database.read() as session:
        sources = await fingerprint_access_service.list_owned_sources(
            session, callback.bot, user_id
        )

    if not sources:
        await callback.message.edit_text(
            _NOTHING_TO_COPY_TEXT, reply_markup=_cancel_keyboard()
        )
        await callback.answer()
        return

    await state.set_state(FingerprintStates.selecting_copy_source)
    await callback.message.edit_text(
        "Выберите сессию, из которой скопировать отпечаток:",
        reply_markup=_copy_source_keyboard(sources),
    )
    await callback.answer()


@router.callback_query(
    F.data.startswith("fp:src:"), FingerprintStates.selecting_copy_source
)
async def pick_copy_source_handler(
    callback: CallbackQuery,
    state: FSMContext,
    database: Database,
    fingerprint_access_service: FingerprintAccessService,
    fingerprint_management_service: FingerprintManagementService,
    fingerprint_resolution_service: FingerprintResolutionService,
) -> None:
    """Copy the chosen owned session's fingerprint onto the current session."""
    if (
        not isinstance(callback.message, Message)
        or not callback.bot
        or not callback.data
    ):
        await callback.answer()
        return

    _, _, raw_chat_id, raw_thread_id = callback.data.split(":")
    source_chat_id, source_thread_id = int(raw_chat_id), int(raw_thread_id)

    target_chat_id = callback.message.chat.id
    target_thread_id = _thread_id(callback.message)
    user_id = callback.from_user.id

    target_owned = await fingerprint_access_service.is_owned(
        callback.bot, user_id, target_chat_id, target_thread_id
    )
    if not target_owned:
        await state.clear()
        await callback.answer("❌ Недостаточно прав.", show_alert=True)
        return

    async with database.read() as session:
        source_binding = await SessionFingerprintRepository(session).get(
            source_chat_id, source_thread_id
        )

    if source_binding is None:
        await state.clear()
        await callback.message.edit_text("❌ Эта сессия больше не существует.")
        await callback.answer()
        return

    source_owned = await fingerprint_access_service.is_owned(
        callback.bot, user_id, source_chat_id, source_thread_id
    )
    if not source_owned:
        await state.clear()
        await callback.answer(
            "❌ Недостаточно прав на исходную сессию.", show_alert=True
        )
        return

    fingerprint_id = source_binding["fingerprint_id"]

    async def _write(session: AsyncSession) -> None:
        await fingerprint_management_service.copy_from(
            session,
            target_chat_id,
            target_thread_id,
            source_fingerprint_id=fingerprint_id,
        )

    await database.write(_write)

    text = await _render_result_card(
        database, fingerprint_resolution_service, target_chat_id, target_thread_id
    )
    await state.clear()
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()


# ---------------------------------------------------------------------------
# Reset + cancel
# ---------------------------------------------------------------------------


@router.callback_query(F.data == "fp:reset")
async def reset_handler(
    callback: CallbackQuery,
    state: FSMContext,
    database: Database,
    fingerprint_access_service: FingerprintAccessService,
    fingerprint_management_service: FingerprintManagementService,
    fingerprint_resolution_service: FingerprintResolutionService,
) -> None:
    """Unbind the session's fingerprint, reverting it to the default profile."""
    if not isinstance(callback.message, Message) or not callback.bot:
        await callback.answer()
        return

    chat_id = callback.message.chat.id
    thread_id = _thread_id(callback.message)
    user_id = callback.from_user.id

    owned = await fingerprint_access_service.is_owned(
        callback.bot, user_id, chat_id, thread_id
    )
    if not owned:
        await callback.answer("❌ Недостаточно прав.", show_alert=True)
        return

    async def _write(session: AsyncSession) -> bool:
        return await fingerprint_management_service.reset(session, chat_id, thread_id)

    was_bound = await database.write(_write)

    if not was_bound:
        await callback.message.edit_text("Отпечаток уже используется по умолчанию.")
        await callback.answer()
        return

    text = await _render_result_card(
        database,
        fingerprint_resolution_service,
        chat_id,
        thread_id,
        extra_note="✅ Сброшено к профилю по умолчанию.",
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "fp:cancel")
async def cancel_handler(callback: CallbackQuery, state: FSMContext) -> None:
    """Clear any in-progress dialog for the clicking user."""
    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    await state.clear()
    await callback.message.edit_text("Отменено.")
    await callback.answer()
