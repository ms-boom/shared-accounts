"""Tests for SQLite PRAGMA configuration."""

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.db.database import register_sqlite_pragmas


@pytest.fixture
async def sqlite_session(tmp_path):
    """Standalone SQLite engine with PRAGMAs registered."""
    db_path = tmp_path / "test_pragmas.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        pool_size=1,
        max_overflow=0,
        connect_args={"check_same_thread": False},
    )
    register_sqlite_pragmas(engine)

    session_maker = async_sessionmaker(engine, class_=AsyncSession)
    async with session_maker() as session:
        yield session

    await engine.dispose()


@pytest.mark.unit
async def test__journal_mode_is_wal(sqlite_session: AsyncSession) -> None:
    result = await sqlite_session.execute(sa.text("PRAGMA journal_mode"))
    assert result.scalar_one() == "wal"


@pytest.mark.unit
async def test__synchronous_is_normal(sqlite_session: AsyncSession) -> None:
    result = await sqlite_session.execute(sa.text("PRAGMA synchronous"))
    assert result.scalar_one() == 1


@pytest.mark.unit
async def test__busy_timeout_is_5000(sqlite_session: AsyncSession) -> None:
    result = await sqlite_session.execute(sa.text("PRAGMA busy_timeout"))
    assert result.scalar_one() == 5000


@pytest.mark.unit
async def test__cache_size_is_64mb(sqlite_session: AsyncSession) -> None:
    result = await sqlite_session.execute(sa.text("PRAGMA cache_size"))
    assert result.scalar_one() == -64000


@pytest.mark.unit
async def test__foreign_keys_enabled(sqlite_session: AsyncSession) -> None:
    result = await sqlite_session.execute(sa.text("PRAGMA foreign_keys"))
    assert result.scalar_one() == 1
