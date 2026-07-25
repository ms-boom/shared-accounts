"""Integration tests for FingerprintManagementService — write side + orphan cleanup."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.repositories.fingerprint_repository import FingerprintRepository
from core.db.repositories.session_fingerprint_repository import (
    SessionFingerprintRepository,
)
from core.exceptions import DatabaseError, FingerprintNotFoundError
from core.fingerprint import FingerprintValues
from core.services.fingerprint_management_service import FingerprintManagementService

EMPTY_VALUES = FingerprintValues(
    user_agent=None,
    cpu_cores=None,
    device_memory=None,
    timezone=None,
    locale=None,
)


@pytest.mark.integration
async def test__set_own__creates_and_binds_new_fingerprint(
    fingerprint_management_service: FingerprintManagementService,
    db_session: AsyncSession,
) -> None:
    values = FingerprintValues(
        user_agent="UA",
        cpu_cores=8,
        device_memory=8,
        timezone="America/New_York",
        locale="en-US",
    )

    fp_id = await fingerprint_management_service.set_own(
        db_session, 111, 0, values=values, created_by=555
    )

    binding = await SessionFingerprintRepository(db_session).get(111, 0)
    assert binding is not None
    assert binding["fingerprint_id"] == fp_id

    stored = await FingerprintRepository(db_session).get_values(fp_id)
    assert stored == values


@pytest.mark.integration
async def test__set_own__generates_label_from_values(
    fingerprint_management_service: FingerprintManagementService,
    db_session: AsyncSession,
) -> None:
    values = FingerprintValues(
        user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/150.0.0.0"),
        cpu_cores=8,
        device_memory=8,
        timezone="America/New_York",
        locale="en-US",
    )

    fp_id = await fingerprint_management_service.set_own(
        db_session, 112, 0, values=values, created_by=1
    )

    fp = await FingerprintRepository(db_session).get(fp_id)
    assert fp is not None
    assert fp["label"] == "Mac · Chrome · 8 ядер / 8 ГБ"


@pytest.mark.integration
async def test__set_own__replacing_an_unshared_binding_deletes_old_fingerprint(
    fingerprint_management_service: FingerprintManagementService,
    db_session: AsyncSession,
) -> None:
    old_fp_id = await fingerprint_management_service.set_own(
        db_session, 222, 0, values=EMPTY_VALUES, created_by=1
    )

    new_fp_id = await fingerprint_management_service.set_own(
        db_session, 222, 0, values=EMPTY_VALUES, created_by=1
    )

    assert new_fp_id != old_fp_id
    assert await FingerprintRepository(db_session).get(old_fp_id) is None


@pytest.mark.integration
async def test__set_own__replacing_a_shared_binding_keeps_still_shared_fingerprint(
    fingerprint_management_service: FingerprintManagementService,
    db_session: AsyncSession,
) -> None:
    shared_fp_id = await fingerprint_management_service.set_own(
        db_session, 333, 0, values=EMPTY_VALUES, created_by=1
    )
    await fingerprint_management_service.copy_from(
        db_session, 334, 0, source_fingerprint_id=shared_fp_id
    )

    await fingerprint_management_service.set_own(
        db_session, 333, 0, values=EMPTY_VALUES, created_by=1
    )

    assert await FingerprintRepository(db_session).get(shared_fp_id) is not None
    assert (
        await SessionFingerprintRepository(db_session).count_for_fingerprint(
            shared_fp_id
        )
        == 1
    )


@pytest.mark.integration
async def test__copy_from__binds_two_sessions_to_one_fingerprint(
    fingerprint_management_service: FingerprintManagementService,
    db_session: AsyncSession,
) -> None:
    source_fp_id = await fingerprint_management_service.set_own(
        db_session, 555, 0, values=EMPTY_VALUES, created_by=1
    )

    await fingerprint_management_service.copy_from(
        db_session, 666, 0, source_fingerprint_id=source_fp_id
    )

    first = await SessionFingerprintRepository(db_session).get(555, 0)
    second = await SessionFingerprintRepository(db_session).get(666, 0)
    assert first is not None
    assert second is not None
    assert first["fingerprint_id"] == second["fingerprint_id"] == source_fp_id
    assert (
        await SessionFingerprintRepository(db_session).count_for_fingerprint(
            source_fp_id
        )
        == 2
    )


@pytest.mark.integration
async def test__copy_from__replacing_own_unshared_binding_deletes_old_fingerprint(
    fingerprint_management_service: FingerprintManagementService,
    db_session: AsyncSession,
) -> None:
    old_fp_id = await fingerprint_management_service.set_own(
        db_session, 700, 0, values=EMPTY_VALUES, created_by=1
    )
    source_fp_id = await fingerprint_management_service.set_own(
        db_session, 701, 0, values=EMPTY_VALUES, created_by=1
    )

    await fingerprint_management_service.copy_from(
        db_session, 700, 0, source_fingerprint_id=source_fp_id
    )

    assert await FingerprintRepository(db_session).get(old_fp_id) is None


@pytest.mark.integration
async def test__edit_shared__changes_are_visible_to_every_bound_session(
    fingerprint_management_service: FingerprintManagementService,
    db_session: AsyncSession,
) -> None:
    fp_id = await fingerprint_management_service.set_own(
        db_session, 777, 0, values=EMPTY_VALUES, created_by=1
    )
    await fingerprint_management_service.copy_from(
        db_session, 888, 0, source_fingerprint_id=fp_id
    )

    new_values = FingerprintValues(
        user_agent="Shared UA",
        cpu_cores=16,
        device_memory=4,
        timezone="Europe/Moscow",
        locale="ru-RU",
    )
    await fingerprint_management_service.edit_shared(
        db_session, fp_id, values=new_values, label="Shared label"
    )

    fp_repo = FingerprintRepository(db_session)
    assert await fp_repo.get_values(fp_id) == new_values

    binding_1 = await SessionFingerprintRepository(db_session).get(777, 0)
    binding_2 = await SessionFingerprintRepository(db_session).get(888, 0)
    assert binding_1 is not None
    assert binding_2 is not None
    assert binding_1["fingerprint_id"] == binding_2["fingerprint_id"] == fp_id


@pytest.mark.integration
async def test__edit_shared__nonexistent_fingerprint_raises_not_found(
    fingerprint_management_service: FingerprintManagementService,
    db_session: AsyncSession,
) -> None:
    with pytest.raises(FingerprintNotFoundError):
        await fingerprint_management_service.edit_shared(
            db_session, 999999, values=EMPTY_VALUES, label="x"
        )


@pytest.mark.integration
async def test__copy_from__invalid_source_fingerprint_id_raises_database_error(
    fingerprint_management_service: FingerprintManagementService,
    db_session: AsyncSession,
) -> None:
    with pytest.raises(DatabaseError):
        await fingerprint_management_service.copy_from(
            db_session, 111222, 0, source_fingerprint_id=999999
        )


@pytest.mark.integration
async def test__reset__unbinds_and_deletes_orphaned_fingerprint(
    fingerprint_management_service: FingerprintManagementService,
    db_session: AsyncSession,
) -> None:
    fp_id = await fingerprint_management_service.set_own(
        db_session, 999, 0, values=EMPTY_VALUES, created_by=1
    )

    result = await fingerprint_management_service.reset(db_session, 999, 0)

    assert result is True
    assert await SessionFingerprintRepository(db_session).get(999, 0) is None
    assert await FingerprintRepository(db_session).get(fp_id) is None


@pytest.mark.integration
async def test__reset__unbinding_keeps_fingerprint_until_last_shared_binding_gone(
    fingerprint_management_service: FingerprintManagementService,
    db_session: AsyncSession,
) -> None:
    fp_id = await fingerprint_management_service.set_own(
        db_session, 1001, 0, values=EMPTY_VALUES, created_by=1
    )
    await fingerprint_management_service.copy_from(
        db_session, 1002, 0, source_fingerprint_id=fp_id
    )

    await fingerprint_management_service.reset(db_session, 1001, 0)
    assert await FingerprintRepository(db_session).get(fp_id) is not None

    await fingerprint_management_service.reset(db_session, 1002, 0)
    assert await FingerprintRepository(db_session).get(fp_id) is None


@pytest.mark.integration
async def test__reset__no_binding_returns_false(
    fingerprint_management_service: FingerprintManagementService,
    db_session: AsyncSession,
) -> None:
    assert await fingerprint_management_service.reset(db_session, 1234567, 0) is False
