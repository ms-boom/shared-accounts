"""Tests for SQLite PRAGMA configuration."""

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.db.database import register_sqlite_pragmas


@pytest.mark.unit
class TestSQLitePragmas:
    """Verify that SQLite PRAGMAs are applied on connection."""

    @pytest.fixture
    async def sqlite_session(self, tmp_path):
        """Create a standalone SQLite engine with PRAGMAs registered."""
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

    async def test_journal_mode_is_wal(self, sqlite_session: AsyncSession) -> None:
        """PRAGMA journal_mode=WAL must be set."""
        result = await sqlite_session.execute(sa.text("PRAGMA journal_mode"))
        value = result.scalar_one()
        assert value == "wal"

    async def test_synchronous_is_normal(self, sqlite_session: AsyncSession) -> None:
        """PRAGMA synchronous=NORMAL (1) must be set."""
        result = await sqlite_session.execute(sa.text("PRAGMA synchronous"))
        value = result.scalar_one()
        assert value == 1  # NORMAL = 1

    async def test_busy_timeout_is_5000(self, sqlite_session: AsyncSession) -> None:
        """PRAGMA busy_timeout=5000 must be set."""
        result = await sqlite_session.execute(sa.text("PRAGMA busy_timeout"))
        value = result.scalar_one()
        assert value == 5000

    async def test_cache_size_is_64mb(self, sqlite_session: AsyncSession) -> None:
        """PRAGMA cache_size=-64000 must be set (negative = KiB)."""
        result = await sqlite_session.execute(sa.text("PRAGMA cache_size"))
        value = result.scalar_one()
        assert value == -64000

    async def test_foreign_keys_enabled(self, sqlite_session: AsyncSession) -> None:
        """PRAGMA foreign_keys=ON must be set."""
        result = await sqlite_session.execute(sa.text("PRAGMA foreign_keys"))
        value = result.scalar_one()
        assert value == 1
