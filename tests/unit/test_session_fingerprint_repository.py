"""Integration tests for SessionFingerprintRepository."""

import pytest

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


async def _make_fingerprint(
    fingerprint_repository: FingerprintRepository, created_by: int = 1
) -> int:
    created = await fingerprint_repository.create(
        values=EMPTY_VALUES, label=None, created_by=created_by
    )
    return int(created["id"])


@pytest.mark.integration
async def test__get__no_binding_returns_none(
    session_fingerprint_repository: SessionFingerprintRepository,
) -> None:
    assert await session_fingerprint_repository.get(123456) is None


@pytest.mark.integration
async def test__bind__creates_new_binding(
    fingerprint_repository: FingerprintRepository,
    session_fingerprint_repository: SessionFingerprintRepository,
) -> None:
    fp_id = await _make_fingerprint(fingerprint_repository)

    bound = await session_fingerprint_repository.bind(111, 0, fp_id)

    assert bound["chat_id"] == 111
    assert bound["thread_id"] == 0
    assert bound["fingerprint_id"] == fp_id

    fetched = await session_fingerprint_repository.get(111, 0)
    assert fetched is not None
    assert fetched["fingerprint_id"] == fp_id


@pytest.mark.integration
async def test__bind__upserts_replacing_existing_binding(
    fingerprint_repository: FingerprintRepository,
    session_fingerprint_repository: SessionFingerprintRepository,
) -> None:
    fp_id_1 = await _make_fingerprint(fingerprint_repository)
    fp_id_2 = await _make_fingerprint(fingerprint_repository)

    await session_fingerprint_repository.bind(222, 0, fp_id_1)
    rebound = await session_fingerprint_repository.bind(222, 0, fp_id_2)

    assert rebound["fingerprint_id"] == fp_id_2

    fetched = await session_fingerprint_repository.get(222, 0)
    assert fetched is not None
    assert fetched["fingerprint_id"] == fp_id_2


@pytest.mark.integration
async def test__bind__default_thread_id_is_main_chat(
    fingerprint_repository: FingerprintRepository,
    session_fingerprint_repository: SessionFingerprintRepository,
) -> None:
    fp_id = await _make_fingerprint(fingerprint_repository)

    await session_fingerprint_repository.bind(333, 0, fp_id)
    main = await session_fingerprint_repository.get(333)

    assert main is not None
    assert main["thread_id"] == 0


@pytest.mark.integration
async def test__bind__isolates_threads_of_same_chat(
    fingerprint_repository: FingerprintRepository,
    session_fingerprint_repository: SessionFingerprintRepository,
) -> None:
    fp_id_main = await _make_fingerprint(fingerprint_repository)
    fp_id_topic = await _make_fingerprint(fingerprint_repository)

    await session_fingerprint_repository.bind(444, 0, fp_id_main)
    await session_fingerprint_repository.bind(444, 99, fp_id_topic)

    main = await session_fingerprint_repository.get(444, 0)
    topic = await session_fingerprint_repository.get(444, 99)

    assert main is not None
    assert topic is not None
    assert main["fingerprint_id"] == fp_id_main
    assert topic["fingerprint_id"] == fp_id_topic


@pytest.mark.integration
async def test__unbind__removes_binding_and_returns_true(
    fingerprint_repository: FingerprintRepository,
    session_fingerprint_repository: SessionFingerprintRepository,
) -> None:
    fp_id = await _make_fingerprint(fingerprint_repository)
    await session_fingerprint_repository.bind(555, 0, fp_id)

    result = await session_fingerprint_repository.unbind(555, 0)

    assert result is True
    assert await session_fingerprint_repository.get(555, 0) is None


@pytest.mark.integration
async def test__unbind__nonexistent_returns_false(
    session_fingerprint_repository: SessionFingerprintRepository,
) -> None:
    assert await session_fingerprint_repository.unbind(999999, 0) is False


@pytest.mark.integration
async def test__count_for_fingerprint__counts_all_bound_sessions(
    fingerprint_repository: FingerprintRepository,
    session_fingerprint_repository: SessionFingerprintRepository,
) -> None:
    fp_id = await _make_fingerprint(fingerprint_repository)
    await session_fingerprint_repository.bind(1, 0, fp_id)
    await session_fingerprint_repository.bind(2, 0, fp_id)
    await session_fingerprint_repository.bind(3, 5, fp_id)

    assert await session_fingerprint_repository.count_for_fingerprint(fp_id) == 3


@pytest.mark.integration
async def test__count_for_fingerprint__zero_when_unbound(
    session_fingerprint_repository: SessionFingerprintRepository,
) -> None:
    assert await session_fingerprint_repository.count_for_fingerprint(999999) == 0


@pytest.mark.integration
async def test__list_for_fingerprint__returns_only_matching_bindings(
    fingerprint_repository: FingerprintRepository,
    session_fingerprint_repository: SessionFingerprintRepository,
) -> None:
    fp_id_1 = await _make_fingerprint(fingerprint_repository)
    fp_id_2 = await _make_fingerprint(fingerprint_repository)
    await session_fingerprint_repository.bind(10, 0, fp_id_1)
    await session_fingerprint_repository.bind(20, 0, fp_id_1)
    await session_fingerprint_repository.bind(30, 0, fp_id_2)

    bindings = await session_fingerprint_repository.list_for_fingerprint(fp_id_1)

    assert {b["chat_id"] for b in bindings} == {10, 20}


@pytest.mark.integration
async def test__list_all__returns_every_binding(
    fingerprint_repository: FingerprintRepository,
    session_fingerprint_repository: SessionFingerprintRepository,
) -> None:
    fp_id = await _make_fingerprint(fingerprint_repository)
    await session_fingerprint_repository.bind(100, 0, fp_id)
    await session_fingerprint_repository.bind(200, 7, fp_id)

    all_bindings = await session_fingerprint_repository.list_all()

    keys = {(b["chat_id"], b["thread_id"]) for b in all_bindings}
    assert keys == {(100, 0), (200, 7)}
