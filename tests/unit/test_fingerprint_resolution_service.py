"""Tests for FingerprintResolutionService — merge (pure) and resolve (DB-backed)."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings
from core.db.repositories.fingerprint_repository import FingerprintRepository
from core.db.repositories.session_fingerprint_repository import (
    SessionFingerprintRepository,
)
from core.fingerprint import EffectiveFingerprint, FingerprintValues
from core.services.fingerprint_resolution_service import FingerprintResolutionService

# ---------------------------------------------------------------------------
# merge — pure, no DB
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test__merge__none_returns_default(
    fingerprint_resolution_service: FingerprintResolutionService,
) -> None:
    merged = fingerprint_resolution_service.merge(None)

    assert merged == fingerprint_resolution_service.default()


@pytest.mark.unit
def test__merge__full_values_override_every_field(
    fingerprint_resolution_service: FingerprintResolutionService,
) -> None:
    values = FingerprintValues(
        user_agent="Custom UA",
        cpu_cores=16,
        device_memory=4,
        timezone="Europe/Moscow",
        locale="ru-RU",
    )

    merged = fingerprint_resolution_service.merge(values)

    assert merged == EffectiveFingerprint(
        user_agent="Custom UA",
        cpu_cores=16,
        device_memory=4,
        timezone="Europe/Moscow",
        locale="ru-RU",
    )


@pytest.mark.unit
def test__merge__partial_values_fall_back_per_field(
    fingerprint_resolution_service: FingerprintResolutionService,
) -> None:
    default = fingerprint_resolution_service.default()
    values = FingerprintValues(
        user_agent="Custom UA",
        cpu_cores=None,
        device_memory=4,
        timezone=None,
        locale=None,
    )

    merged = fingerprint_resolution_service.merge(values)

    assert merged.user_agent == "Custom UA"
    assert merged.cpu_cores == default.cpu_cores
    assert merged.device_memory == 4
    assert merged.timezone == default.timezone
    assert merged.locale == default.locale


@pytest.mark.unit
def test__default__is_built_from_settings_and_is_stable(
    fingerprint_resolution_service: FingerprintResolutionService,
    test_settings: Settings,
) -> None:
    default = fingerprint_resolution_service.default()

    assert default.user_agent == test_settings.DEFAULT_USER_AGENT
    assert default.cpu_cores == test_settings.DEFAULT_CPU_CORES
    assert default.device_memory == test_settings.DEFAULT_DEVICE_MEMORY
    assert default.timezone == test_settings.DEFAULT_TIMEZONE
    assert default.locale == test_settings.DEFAULT_LOCALE
    assert fingerprint_resolution_service.default() is default


# ---------------------------------------------------------------------------
# resolve — DB-backed
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test__resolve__no_binding_returns_default(
    fingerprint_resolution_service: FingerprintResolutionService,
    db_session: AsyncSession,
) -> None:
    effective = await fingerprint_resolution_service.resolve(db_session, 999999, 0)

    assert effective == fingerprint_resolution_service.default()


@pytest.mark.integration
async def test__resolve__binding_with_full_values(
    fingerprint_resolution_service: FingerprintResolutionService,
    db_session: AsyncSession,
) -> None:
    fp_repo = FingerprintRepository(db_session)
    values = FingerprintValues(
        user_agent="Custom UA",
        cpu_cores=16,
        device_memory=4,
        timezone="Europe/Moscow",
        locale="ru-RU",
    )
    created = await fp_repo.create(values=values, label="l", created_by=1)
    await SessionFingerprintRepository(db_session).bind(555, 0, created["id"])

    effective = await fingerprint_resolution_service.resolve(db_session, 555, 0)

    assert effective == EffectiveFingerprint(
        user_agent="Custom UA",
        cpu_cores=16,
        device_memory=4,
        timezone="Europe/Moscow",
        locale="ru-RU",
    )


@pytest.mark.integration
async def test__resolve__binding_with_partial_values_falls_back_per_field(
    fingerprint_resolution_service: FingerprintResolutionService,
    db_session: AsyncSession,
) -> None:
    fp_repo = FingerprintRepository(db_session)
    values = FingerprintValues(
        user_agent=None, cpu_cores=16, device_memory=None, timezone=None, locale=None
    )
    created = await fp_repo.create(values=values, label=None, created_by=1)
    await SessionFingerprintRepository(db_session).bind(666, 0, created["id"])

    effective = await fingerprint_resolution_service.resolve(db_session, 666, 0)
    default = fingerprint_resolution_service.default()

    assert effective.cpu_cores == 16
    assert effective.user_agent == default.user_agent
    assert effective.device_memory == default.device_memory
    assert effective.timezone == default.timezone
    assert effective.locale == default.locale


@pytest.mark.integration
async def test__resolve__isolated_by_thread_id(
    fingerprint_resolution_service: FingerprintResolutionService,
    db_session: AsyncSession,
) -> None:
    fp_repo = FingerprintRepository(db_session)
    values = FingerprintValues(
        user_agent="Topic UA",
        cpu_cores=None,
        device_memory=None,
        timezone=None,
        locale=None,
    )
    created = await fp_repo.create(values=values, label=None, created_by=1)
    await SessionFingerprintRepository(db_session).bind(777, 42, created["id"])

    main_effective = await fingerprint_resolution_service.resolve(db_session, 777, 0)
    topic_effective = await fingerprint_resolution_service.resolve(db_session, 777, 42)

    assert main_effective == fingerprint_resolution_service.default()
    assert topic_effective.user_agent == "Topic UA"


# ---------------------------------------------------------------------------
# resolve_view
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test__resolve_view__no_binding_all_fields_default(
    fingerprint_resolution_service: FingerprintResolutionService,
    db_session: AsyncSession,
) -> None:
    view = await fingerprint_resolution_service.resolve_view(db_session, 888888, 0)

    assert view.effective == fingerprint_resolution_service.default()
    assert set(view.source.values()) == {"default"}
    assert view.shared_session_count == 0
    assert view.label is None


@pytest.mark.integration
async def test__resolve_view__partial_binding_marks_only_set_fields_own(
    fingerprint_resolution_service: FingerprintResolutionService,
    db_session: AsyncSession,
) -> None:
    fp_repo = FingerprintRepository(db_session)
    values = FingerprintValues(
        user_agent="Custom UA",
        cpu_cores=None,
        device_memory=None,
        timezone=None,
        locale=None,
    )
    created = await fp_repo.create(values=values, label="My label", created_by=1)
    await SessionFingerprintRepository(db_session).bind(999, 0, created["id"])

    view = await fingerprint_resolution_service.resolve_view(db_session, 999, 0)

    assert view.source["user_agent"] == "own"
    assert view.source["cpu_cores"] == "default"
    assert view.source["device_memory"] == "default"
    assert view.source["timezone"] == "default"
    assert view.source["locale"] == "default"
    assert view.label == "My label"
    assert view.shared_session_count == 1


@pytest.mark.integration
async def test__resolve_view__shared_session_count_reflects_all_bindings(
    fingerprint_resolution_service: FingerprintResolutionService,
    db_session: AsyncSession,
) -> None:
    fp_repo = FingerprintRepository(db_session)
    created = await fp_repo.create(
        values=FingerprintValues(
            user_agent=None,
            cpu_cores=None,
            device_memory=None,
            timezone=None,
            locale=None,
        ),
        label=None,
        created_by=1,
    )
    session_fp_repo = SessionFingerprintRepository(db_session)
    await session_fp_repo.bind(1000, 0, created["id"])
    await session_fp_repo.bind(2000, 0, created["id"])

    view = await fingerprint_resolution_service.resolve_view(db_session, 1000, 0)

    assert view.shared_session_count == 2
