"""Tests for SQLiteWriterQueue."""

import asyncio

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from core.db.database import SQLiteWriterQueue, register_sqlite_pragmas


class _Base(DeclarativeBase):
    pass


class _Counter(_Base):
    __tablename__ = "test_counter"
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    value: Mapped[int] = mapped_column(default=0)


async def _make_env(tmp_path):
    db_path = tmp_path / "test_writer_queue.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        pool_size=1,
        max_overflow=0,
        connect_args={"check_same_thread": False},
    )
    register_sqlite_pragmas(engine)

    async with engine.begin() as conn:
        await conn.run_sync(_Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession)
    return session_maker, engine


@pytest.mark.unit
async def test__execute__returns_result(tmp_path) -> None:
    session_maker, engine = await _make_env(tmp_path)
    queue = SQLiteWriterQueue(session_maker)
    await queue.start()
    try:

        async def write_fn(session: AsyncSession) -> str:
            return "hello"

        assert await queue.execute(write_fn) == "hello"
    finally:
        await queue.stop()
        await engine.dispose()


@pytest.mark.unit
async def test__execute__writes_to_db(tmp_path) -> None:
    session_maker, engine = await _make_env(tmp_path)
    queue = SQLiteWriterQueue(session_maker)
    await queue.start()
    try:

        async def insert_counter(session: AsyncSession) -> None:
            session.add(_Counter(id=1, value=42))

        await queue.execute(insert_counter)

        async with session_maker() as session:
            result = await session.execute(
                sa.select(_Counter.value).where(_Counter.id == 1)
            )
            assert result.scalar_one() == 42
    finally:
        await queue.stop()
        await engine.dispose()


@pytest.mark.unit
async def test__execute__propagates_exception(tmp_path) -> None:
    session_maker, engine = await _make_env(tmp_path)
    queue = SQLiteWriterQueue(session_maker)
    await queue.start()
    try:

        async def failing_fn(session: AsyncSession) -> None:
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            await queue.execute(failing_fn)
    finally:
        await queue.stop()
        await engine.dispose()


@pytest.mark.unit
async def test__execute__rolls_back_on_error(tmp_path) -> None:
    session_maker, engine = await _make_env(tmp_path)
    queue = SQLiteWriterQueue(session_maker)
    await queue.start()
    try:

        async def failing_insert(session: AsyncSession) -> None:
            session.add(_Counter(id=99, value=1))
            await session.flush()
            raise RuntimeError("rollback me")

        with pytest.raises(RuntimeError, match="rollback me"):
            await queue.execute(failing_insert)

        async with session_maker() as session:
            result = await session.execute(
                sa.select(_Counter).where(_Counter.id == 99)
            )
            assert result.scalar_one_or_none() is None
    finally:
        await queue.stop()
        await engine.dispose()


@pytest.mark.unit
async def test__serializes_concurrent_writes(tmp_path) -> None:
    session_maker, engine = await _make_env(tmp_path)
    queue = SQLiteWriterQueue(session_maker)
    await queue.start()
    try:

        async def seed(session: AsyncSession) -> None:
            session.add(_Counter(id=1, value=0))

        await queue.execute(seed)

        async def increment(session: AsyncSession) -> None:
            result = await session.execute(
                sa.select(_Counter.value).where(_Counter.id == 1)
            )
            current = result.scalar_one()
            await session.execute(
                sa.update(_Counter)
                .where(_Counter.id == 1)
                .values(value=current + 1)
            )

        await asyncio.gather(*(queue.execute(increment) for _ in range(10)))

        async with session_maker() as session:
            result = await session.execute(
                sa.select(_Counter.value).where(_Counter.id == 1)
            )
            assert result.scalar_one() == 10
    finally:
        await queue.stop()
        await engine.dispose()


@pytest.mark.unit
async def test__execute_after_stop__raises(tmp_path) -> None:
    session_maker, engine = await _make_env(tmp_path)
    queue = SQLiteWriterQueue(session_maker)
    await queue.start()
    await queue.stop()
    try:
        with pytest.raises(RuntimeError, match="stopped"):
            await queue.execute(lambda s: s.execute(sa.text("SELECT 1")))
    finally:
        await engine.dispose()


@pytest.mark.unit
async def test__stop__returns_normally(tmp_path) -> None:
    session_maker, engine = await _make_env(tmp_path)
    queue = SQLiteWriterQueue(session_maker)
    await queue.start()
    await queue.stop()
    await engine.dispose()
