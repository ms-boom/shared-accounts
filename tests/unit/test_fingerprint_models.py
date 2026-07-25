"""Round-trip and constraint tests for the Fingerprint / SessionFingerprint models."""

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import Fingerprint, SessionFingerprint


@pytest.mark.integration
async def test__fingerprint_and_binding__round_trip(db_session: AsyncSession) -> None:
    fingerprint = Fingerprint(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        cpu_cores=8,
        device_memory=8,
        timezone="America/New_York",
        locale="en-US",
        label="Mac · Chrome · 8 cores / 8 GB",
        created_by=123456789,
    )
    db_session.add(fingerprint)
    await db_session.flush()

    binding = SessionFingerprint(
        chat_id=-100123456789,
        thread_id=42,
        fingerprint_id=fingerprint.id,
    )
    db_session.add(binding)
    await db_session.flush()

    fp_row = await db_session.get(Fingerprint, fingerprint.id)
    assert fp_row is not None
    assert fp_row.user_agent == "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    assert fp_row.cpu_cores == 8
    assert fp_row.device_memory == 8
    assert fp_row.timezone == "America/New_York"
    assert fp_row.locale == "en-US"
    assert fp_row.label == "Mac · Chrome · 8 cores / 8 GB"
    assert fp_row.created_by == 123456789
    assert fp_row.created_at is not None
    assert fp_row.updated_at is not None

    binding_row = await db_session.get(SessionFingerprint, (-100123456789, 42))
    assert binding_row is not None
    assert binding_row.fingerprint_id == fingerprint.id
    assert binding_row.created_at is not None
    assert binding_row.updated_at is not None


@pytest.mark.integration
async def test__fingerprint__value_fields_are_nullable(
    db_session: AsyncSession,
) -> None:
    fingerprint = Fingerprint(created_by=1)
    db_session.add(fingerprint)
    await db_session.flush()

    row = await db_session.get(Fingerprint, fingerprint.id)
    assert row is not None
    assert row.user_agent is None
    assert row.cpu_cores is None
    assert row.device_memory is None
    assert row.timezone is None
    assert row.locale is None
    assert row.label is None


@pytest.mark.integration
async def test__session_fingerprint__thread_id_defaults_to_zero(
    db_session: AsyncSession,
) -> None:
    fingerprint = Fingerprint(created_by=1)
    db_session.add(fingerprint)
    await db_session.flush()

    db_session.add(SessionFingerprint(chat_id=555, fingerprint_id=fingerprint.id))
    await db_session.flush()

    stmt = sa.select(SessionFingerprint).where(SessionFingerprint.chat_id == 555)
    result = await db_session.execute(stmt)
    row = result.scalar_one()
    assert row.thread_id == 0


@pytest.mark.integration
async def test__session_fingerprint__composite_pk_enforced(
    db_session: AsyncSession,
) -> None:
    fingerprint = Fingerprint(created_by=1)
    db_session.add(fingerprint)
    await db_session.flush()

    db_session.add(
        SessionFingerprint(chat_id=1, thread_id=0, fingerprint_id=fingerprint.id)
    )
    await db_session.flush()

    db_session.add(
        SessionFingerprint(chat_id=1, thread_id=0, fingerprint_id=fingerprint.id)
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.integration
async def test__session_fingerprint__two_threads_of_same_chat_coexist(
    db_session: AsyncSession,
) -> None:
    fingerprint = Fingerprint(created_by=1)
    db_session.add(fingerprint)
    await db_session.flush()

    db_session.add(
        SessionFingerprint(chat_id=1, thread_id=0, fingerprint_id=fingerprint.id)
    )
    db_session.add(
        SessionFingerprint(chat_id=1, thread_id=99, fingerprint_id=fingerprint.id)
    )
    await db_session.flush()

    stmt = (
        sa.select(sa.func.count())
        .select_from(SessionFingerprint)
        .where(SessionFingerprint.chat_id == 1)
    )
    result = await db_session.execute(stmt)
    assert result.scalar_one() == 2


@pytest.mark.integration
async def test__session_fingerprint__fk_to_fingerprint_enforced(
    db_session: AsyncSession,
) -> None:
    db_session.add(SessionFingerprint(chat_id=2, thread_id=0, fingerprint_id=999999))
    with pytest.raises(IntegrityError):
        await db_session.flush()
