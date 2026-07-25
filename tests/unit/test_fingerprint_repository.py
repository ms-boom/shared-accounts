"""Integration tests for FingerprintRepository."""

import pytest

from core.db.repositories.fingerprint_repository import FingerprintRepository
from core.fingerprint import FingerprintValues

FULL_VALUES = FingerprintValues(
    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    cpu_cores=8,
    device_memory=8,
    timezone="America/New_York",
    locale="en-US",
)

EMPTY_VALUES = FingerprintValues(
    user_agent=None,
    cpu_cores=None,
    device_memory=None,
    timezone=None,
    locale=None,
)


@pytest.mark.integration
async def test__create__stores_full_values(
    fingerprint_repository: FingerprintRepository,
) -> None:
    created = await fingerprint_repository.create(
        values=FULL_VALUES, label="Mac · Chrome · 8 ядер / 8 ГБ", created_by=111
    )

    assert created["user_agent"] == FULL_VALUES.user_agent
    assert created["cpu_cores"] == 8
    assert created["device_memory"] == 8
    assert created["timezone"] == "America/New_York"
    assert created["locale"] == "en-US"
    assert created["label"] == "Mac · Chrome · 8 ядер / 8 ГБ"
    assert created["created_by"] == 111
    assert created["id"] is not None


@pytest.mark.integration
async def test__create__allows_partial_values(
    fingerprint_repository: FingerprintRepository,
) -> None:
    partial = FingerprintValues(
        user_agent=None, cpu_cores=4, device_memory=2, timezone=None, locale=None
    )

    created = await fingerprint_repository.create(
        values=partial, label=None, created_by=1
    )

    assert created["user_agent"] is None
    assert created["cpu_cores"] == 4
    assert created["device_memory"] == 2
    assert created["timezone"] is None
    assert created["locale"] is None
    assert created["label"] is None


@pytest.mark.integration
async def test__get_values__returns_stored_values(
    fingerprint_repository: FingerprintRepository,
) -> None:
    created = await fingerprint_repository.create(
        values=FULL_VALUES, label="l", created_by=1
    )

    values = await fingerprint_repository.get_values(created["id"])

    assert values == FULL_VALUES


@pytest.mark.integration
async def test__get_values__nonexistent_returns_none(
    fingerprint_repository: FingerprintRepository,
) -> None:
    assert await fingerprint_repository.get_values(999999) is None


@pytest.mark.integration
async def test__get__returns_full_row(
    fingerprint_repository: FingerprintRepository,
) -> None:
    created = await fingerprint_repository.create(
        values=FULL_VALUES, label="l", created_by=42
    )

    row = await fingerprint_repository.get(created["id"])

    assert row is not None
    assert row["id"] == created["id"]
    assert row["created_by"] == 42
    assert row["label"] == "l"
    assert row["user_agent"] == FULL_VALUES.user_agent


@pytest.mark.integration
async def test__get__nonexistent_returns_none(
    fingerprint_repository: FingerprintRepository,
) -> None:
    assert await fingerprint_repository.get(999999) is None


@pytest.mark.integration
async def test__get_many__returns_mapping_of_id_to_row_for_existing_ids(
    fingerprint_repository: FingerprintRepository,
) -> None:
    first = await fingerprint_repository.create(
        values=FULL_VALUES, label="a", created_by=1
    )
    second = await fingerprint_repository.create(
        values=EMPTY_VALUES, label="b", created_by=1
    )

    rows = await fingerprint_repository.get_many([first["id"], second["id"]])

    assert set(rows.keys()) == {first["id"], second["id"]}
    assert rows[first["id"]]["label"] == "a"
    assert rows[second["id"]]["label"] == "b"


@pytest.mark.integration
async def test__get_many__omits_nonexistent_ids(
    fingerprint_repository: FingerprintRepository,
) -> None:
    created = await fingerprint_repository.create(
        values=FULL_VALUES, label="a", created_by=1
    )

    rows = await fingerprint_repository.get_many([created["id"], 999999])

    assert set(rows.keys()) == {created["id"]}


@pytest.mark.integration
async def test__get_many__empty_input_returns_empty_dict(
    fingerprint_repository: FingerprintRepository,
) -> None:
    assert await fingerprint_repository.get_many([]) == {}


@pytest.mark.integration
async def test__update_values__overwrites_all_value_fields(
    fingerprint_repository: FingerprintRepository,
) -> None:
    created = await fingerprint_repository.create(
        values=EMPTY_VALUES, label=None, created_by=1
    )

    updated = await fingerprint_repository.update_values(
        created["id"], FULL_VALUES, "new label"
    )

    assert updated is not None
    assert updated["user_agent"] == FULL_VALUES.user_agent
    assert updated["cpu_cores"] == 8
    assert updated["label"] == "new label"

    reread = await fingerprint_repository.get_values(created["id"])
    assert reread == FULL_VALUES


@pytest.mark.integration
async def test__update_values__can_clear_a_field_back_to_none(
    fingerprint_repository: FingerprintRepository,
) -> None:
    created = await fingerprint_repository.create(
        values=FULL_VALUES, label="l", created_by=1
    )

    cleared = FingerprintValues(
        user_agent=None,
        cpu_cores=FULL_VALUES.cpu_cores,
        device_memory=FULL_VALUES.device_memory,
        timezone=FULL_VALUES.timezone,
        locale=FULL_VALUES.locale,
    )
    updated = await fingerprint_repository.update_values(created["id"], cleared, "l")

    assert updated is not None
    assert updated["user_agent"] is None


@pytest.mark.integration
async def test__update_values__nonexistent_returns_none(
    fingerprint_repository: FingerprintRepository,
) -> None:
    result = await fingerprint_repository.update_values(999999, FULL_VALUES, "x")
    assert result is None


@pytest.mark.integration
async def test__delete__removes_row_and_returns_true(
    fingerprint_repository: FingerprintRepository,
) -> None:
    created = await fingerprint_repository.create(
        values=EMPTY_VALUES, label=None, created_by=1
    )

    result = await fingerprint_repository.delete(created["id"])

    assert result is True
    assert await fingerprint_repository.get(created["id"]) is None


@pytest.mark.integration
async def test__delete__nonexistent_returns_false(
    fingerprint_repository: FingerprintRepository,
) -> None:
    assert await fingerprint_repository.delete(999999) is False
