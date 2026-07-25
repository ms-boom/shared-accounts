"""Tests for FingerprintAccessService — ownership checks and owned-source listing."""

from unittest.mock import MagicMock

import pytest
from aiogram.types import ChatMember
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.fingerprint_access_service import FingerprintAccessService
from core.db.repositories.fingerprint_repository import FingerprintRepository
from core.db.repositories.session_fingerprint_repository import (
    SessionFingerprintRepository,
)
from core.fingerprint import FingerprintValues

EMPTY_VALUES = FingerprintValues(
    user_agent=None,
    cpu_cores=None,
    device_memory=None,
    timezone=None,
    locale=None,
)

# ---------------------------------------------------------------------------
# is_owned
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test__is_owned__private_chat_matches_own_user_id(
    fingerprint_access_service: FingerprintAccessService,
    mock_bot: MagicMock,
) -> None:
    owned = await fingerprint_access_service.is_owned(
        mock_bot, user_id=123, chat_id=123, thread_id=0
    )

    assert owned is True
    mock_bot.get_chat_member.assert_not_called()


@pytest.mark.unit
async def test__is_owned__private_chat_rejects_foreign_user_id(
    fingerprint_access_service: FingerprintAccessService,
    mock_bot: MagicMock,
) -> None:
    owned = await fingerprint_access_service.is_owned(
        mock_bot, user_id=123, chat_id=456, thread_id=0
    )

    assert owned is False
    mock_bot.get_chat_member.assert_not_called()


@pytest.mark.unit
async def test__is_owned__group_uses_admin_check(
    fingerprint_access_service: FingerprintAccessService,
    mock_bot: MagicMock,
    mock_admin_member: ChatMember,
) -> None:
    mock_bot.get_chat_member.return_value = mock_admin_member

    owned = await fingerprint_access_service.is_owned(
        mock_bot, user_id=123, chat_id=-100123456789, thread_id=0
    )

    assert owned is True
    mock_bot.get_chat_member.assert_called_once_with(-100123456789, 123)


@pytest.mark.unit
async def test__is_owned__foreign_group_denied_for_non_admin(
    fingerprint_access_service: FingerprintAccessService,
    mock_bot: MagicMock,
    mock_regular_member: ChatMember,
) -> None:
    mock_bot.get_chat_member.return_value = mock_regular_member

    owned = await fingerprint_access_service.is_owned(
        mock_bot, user_id=789, chat_id=-100987654321, thread_id=0
    )

    assert owned is False


@pytest.mark.unit
async def test__is_owned__topic_thread_never_matches_private_shortcut(
    fingerprint_access_service: FingerprintAccessService,
    mock_bot: MagicMock,
    mock_admin_member: ChatMember,
) -> None:
    """A topic (thread_id>0) only exists in a group (chat_id<0); user_id is
    always positive, so chat_id == user_id can never hold here — ownership
    must always fall through to the group admin check, never the private
    shortcut."""
    mock_bot.get_chat_member.return_value = mock_admin_member

    owned = await fingerprint_access_service.is_owned(
        mock_bot, user_id=123, chat_id=-100123456789, thread_id=42
    )

    assert owned is True
    mock_bot.get_chat_member.assert_called_once_with(-100123456789, 123)


# ---------------------------------------------------------------------------
# list_owned_sources
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test__list_owned_sources__excludes_foreign_group(
    fingerprint_access_service: FingerprintAccessService,
    mock_bot: MagicMock,
    mock_admin_member: ChatMember,
    mock_regular_member: ChatMember,
    db_session: AsyncSession,
) -> None:
    fp_repo = FingerprintRepository(db_session)
    session_fp_repo = SessionFingerprintRepository(db_session)
    owned_fp = await fp_repo.create(values=EMPTY_VALUES, label="mine", created_by=1)
    foreign_fp = await fp_repo.create(
        values=EMPTY_VALUES, label="foreign", created_by=2
    )
    await session_fp_repo.bind(-100111, 0, owned_fp["id"])
    await session_fp_repo.bind(-100222, 0, foreign_fp["id"])

    async def _get_chat_member(chat_id: int, user_id: int) -> ChatMember:
        return mock_admin_member if chat_id == -100111 else mock_regular_member

    mock_bot.get_chat_member.side_effect = _get_chat_member

    sources = await fingerprint_access_service.list_owned_sources(
        db_session, mock_bot, 123
    )

    chat_ids = {s["chat_id"] for s in sources}
    assert chat_ids == {-100111}


@pytest.mark.integration
async def test__list_owned_sources__includes_own_private_session(
    fingerprint_access_service: FingerprintAccessService,
    mock_bot: MagicMock,
    db_session: AsyncSession,
) -> None:
    fp_repo = FingerprintRepository(db_session)
    session_fp_repo = SessionFingerprintRepository(db_session)
    fp = await fp_repo.create(values=EMPTY_VALUES, label="mine", created_by=1)
    await session_fp_repo.bind(123, 0, fp["id"])

    sources = await fingerprint_access_service.list_owned_sources(
        db_session, mock_bot, 123
    )

    assert len(sources) == 1
    assert sources[0]["chat_id"] == 123
    assert sources[0]["thread_id"] == 0
    assert sources[0]["fingerprint_id"] == fp["id"]
    assert sources[0]["label"] == "mine"
    mock_bot.get_chat_member.assert_not_called()


@pytest.mark.integration
async def test__list_owned_sources__batched_fetch_preserves_entry_shape_and_excludes_foreign(
    fingerprint_access_service: FingerprintAccessService,
    mock_bot: MagicMock,
    mock_admin_member: ChatMember,
    mock_regular_member: ChatMember,
    db_session: AsyncSession,
) -> None:
    """N+1 -> batched fetch must not change the entry shape or which
    bindings are returned: foreign group still excluded, own binding still
    included with its full flattened value fields."""
    fp_repo = FingerprintRepository(db_session)
    session_fp_repo = SessionFingerprintRepository(db_session)
    owned_fp = await fp_repo.create(
        values=FingerprintValues(
            user_agent="UA",
            cpu_cores=8,
            device_memory=8,
            timezone="America/New_York",
            locale="en-US",
        ),
        label="mine",
        created_by=1,
    )
    foreign_fp = await fp_repo.create(
        values=EMPTY_VALUES, label="foreign", created_by=2
    )
    await session_fp_repo.bind(-100111, 0, owned_fp["id"])
    await session_fp_repo.bind(-100222, 0, foreign_fp["id"])

    async def _get_chat_member(chat_id: int, user_id: int) -> ChatMember:
        return mock_admin_member if chat_id == -100111 else mock_regular_member

    mock_bot.get_chat_member.side_effect = _get_chat_member

    sources = await fingerprint_access_service.list_owned_sources(
        db_session, mock_bot, 123
    )

    assert len(sources) == 1
    assert sources[0] == {
        "chat_id": -100111,
        "thread_id": 0,
        "fingerprint_id": owned_fp["id"],
        "label": "mine",
        "user_agent": "UA",
        "cpu_cores": 8,
        "device_memory": 8,
        "timezone": "America/New_York",
        "locale": "en-US",
    }


@pytest.mark.integration
async def test__list_owned_sources__empty_when_no_bindings_exist(
    fingerprint_access_service: FingerprintAccessService,
    mock_bot: MagicMock,
    db_session: AsyncSession,
) -> None:
    sources = await fingerprint_access_service.list_owned_sources(
        db_session, mock_bot, 123
    )

    assert sources == []


# ---------------------------------------------------------------------------
# can_edit_fingerprint
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test__can_edit_fingerprint__true_when_user_owns_at_least_one_bound_session(
    fingerprint_access_service: FingerprintAccessService,
    mock_bot: MagicMock,
    mock_admin_member: ChatMember,
    db_session: AsyncSession,
) -> None:
    fp_repo = FingerprintRepository(db_session)
    session_fp_repo = SessionFingerprintRepository(db_session)
    fp = await fp_repo.create(values=EMPTY_VALUES, label=None, created_by=1)
    await session_fp_repo.bind(-100333, 0, fp["id"])
    mock_bot.get_chat_member.return_value = mock_admin_member

    can_edit = await fingerprint_access_service.can_edit_fingerprint(
        db_session, mock_bot, 123, fp["id"]
    )

    assert can_edit is True


@pytest.mark.integration
async def test__can_edit_fingerprint__false_when_user_owns_none_of_the_bound_sessions(
    fingerprint_access_service: FingerprintAccessService,
    mock_bot: MagicMock,
    mock_regular_member: ChatMember,
    db_session: AsyncSession,
) -> None:
    fp_repo = FingerprintRepository(db_session)
    session_fp_repo = SessionFingerprintRepository(db_session)
    fp = await fp_repo.create(values=EMPTY_VALUES, label=None, created_by=1)
    await session_fp_repo.bind(-100444, 0, fp["id"])
    mock_bot.get_chat_member.return_value = mock_regular_member

    can_edit = await fingerprint_access_service.can_edit_fingerprint(
        db_session, mock_bot, 123, fp["id"]
    )

    assert can_edit is False


@pytest.mark.integration
async def test__can_edit_fingerprint__co_admins_of_same_group_both_can_edit(
    fingerprint_access_service: FingerprintAccessService,
    mock_bot: MagicMock,
    mock_admin_member: ChatMember,
    db_session: AsyncSession,
) -> None:
    fp_repo = FingerprintRepository(db_session)
    session_fp_repo = SessionFingerprintRepository(db_session)
    fp = await fp_repo.create(values=EMPTY_VALUES, label=None, created_by=1)
    await session_fp_repo.bind(-100555, 0, fp["id"])
    mock_bot.get_chat_member.return_value = mock_admin_member

    first_admin_can_edit = await fingerprint_access_service.can_edit_fingerprint(
        db_session, mock_bot, 111, fp["id"]
    )
    second_admin_can_edit = await fingerprint_access_service.can_edit_fingerprint(
        db_session, mock_bot, 222, fp["id"]
    )

    assert first_admin_can_edit is True
    assert second_admin_can_edit is True
