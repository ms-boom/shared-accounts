"""Upgrade/downgrade round-trip tests for the fingerprint schema migration.

Exercises `migrations/versions/002_fingerprints.py` directly through Alembic
against isolated temp SQLite files (no shared test-database fixtures), so this
does not contend with the transactional `db_session` fixture used elsewhere.
"""

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config


def _alembic_config() -> Config:
    return Config("alembic.ini")


def _table_names(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    return {row[0] for row in rows}


def _table_columns(db_path: Path, table_name: str) -> list[tuple]:
    """(name, type, notnull, default, pk) per column, order-sensitive."""
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [(r[1], r[2], r[3], r[4], r[5]) for r in rows]


def _index_names(db_path: Path, table_name: str) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(f"PRAGMA index_list({table_name})").fetchall()
    return {r[1] for r in rows}


def _foreign_keys(db_path: Path, table_name: str) -> set[tuple]:
    """(referenced table, local column, referenced column) per FK."""
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(f"PRAGMA foreign_key_list({table_name})").fetchall()
    return {(r[2], r[3], r[4]) for r in rows}


@pytest.fixture
def migration_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point env.py's get_settings() at an isolated temp SQLite file.

    env.py overwrites the Config's sqlalchemy.url with settings.DATABASE_URL
    on every run, so the URL must be provided via the environment.
    """
    db_path = tmp_path / "migration.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    return db_path


@pytest.mark.unit
def test__upgrade_head__creates_fingerprint_tables(migration_db: Path) -> None:
    command.upgrade(_alembic_config(), "head")

    tables = _table_names(migration_db)
    assert "fingerprints" in tables
    assert "session_fingerprints" in tables


@pytest.mark.unit
def test__upgrade_head__session_fingerprints_has_fingerprint_id_index(
    migration_db: Path,
) -> None:
    command.upgrade(_alembic_config(), "head")

    assert "ix_session_fingerprints_fingerprint_id" in _index_names(
        migration_db, "session_fingerprints"
    )


@pytest.mark.unit
def test__upgrade_head__session_fingerprints_fk_targets_fingerprints(
    migration_db: Path,
) -> None:
    command.upgrade(_alembic_config(), "head")

    fks = _foreign_keys(migration_db, "session_fingerprints")
    assert ("fingerprints", "fingerprint_id", "id") in fks


@pytest.mark.unit
def test__downgrade_to_001__drops_fingerprint_tables(migration_db: Path) -> None:
    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    command.downgrade(cfg, "001")

    tables = _table_names(migration_db)
    assert "fingerprints" not in tables
    assert "session_fingerprints" not in tables


@pytest.mark.unit
def test__downgrade_to_001__leaves_other_tables_untouched(migration_db: Path) -> None:
    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    command.downgrade(cfg, "001")

    tables = _table_names(migration_db)
    assert {"groups", "users", "chat_sessions", "tasks", "fsm_states"} <= tables


@pytest.mark.unit
def test__round_trip__schema_identical_to_fresh_upgrade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """upgrade -> downgrade(001) -> upgrade(head) must match a single fresh upgrade."""
    round_trip_db = tmp_path / "round_trip.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{round_trip_db}")
    round_trip_cfg = _alembic_config()

    command.upgrade(round_trip_cfg, "head")
    command.downgrade(round_trip_cfg, "001")
    command.upgrade(round_trip_cfg, "head")

    fresh_db = tmp_path / "fresh.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{fresh_db}")
    fresh_cfg = _alembic_config()
    command.upgrade(fresh_cfg, "head")

    for table in ("fingerprints", "session_fingerprints"):
        assert _table_columns(round_trip_db, table) == _table_columns(fresh_db, table)
        assert _index_names(round_trip_db, table) == _index_names(fresh_db, table)
        assert _foreign_keys(round_trip_db, table) == _foreign_keys(fresh_db, table)
