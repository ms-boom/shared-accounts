"""Tests for BotFSMStorage — data get/set/update operations."""

import pytest
from aiogram.fsm.storage.base import StorageKey
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.db.fsm_storage import BotFSMStorage
from core.db.database import SQLiteWriterQueue, register_sqlite_pragmas
from core.db.models import Base


def _key(
    chat_id: int = 100, user_id: int = 200, thread_id: int | None = None
) -> StorageKey:
    return StorageKey(bot_id=1, chat_id=chat_id, user_id=user_id, thread_id=thread_id)


async def _make_storage(tmp_path):
    db_path = tmp_path / "fsm_test.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        pool_size=1,
        max_overflow=0,
        connect_args={"check_same_thread": False},
    )
    register_sqlite_pragmas(engine)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession)
    writer_queue = SQLiteWriterQueue(session_maker)
    await writer_queue.start()

    class _FakeDatabase:
        async def write(self, fn):
            return await writer_queue.execute(fn)

        def read(self):
            return session_maker()

    storage = BotFSMStorage(_FakeDatabase())
    return storage, writer_queue, engine


@pytest.mark.unit
async def test__set_data__roundtrip(tmp_path) -> None:
    storage, queue, engine = await _make_storage(tmp_path)
    try:
        key = _key()
        await storage.set_data(key, {"email": "test@example.com", "step": 2})
        assert await storage.get_data(key) == {"email": "test@example.com", "step": 2}
    finally:
        await queue.stop()
        await engine.dispose()


@pytest.mark.unit
async def test__get_data__no_row__returns_empty_dict(tmp_path) -> None:
    storage, queue, engine = await _make_storage(tmp_path)
    try:
        assert await storage.get_data(_key(chat_id=999)) == {}
    finally:
        await queue.stop()
        await engine.dispose()


@pytest.mark.unit
async def test__set_data__overwrites_previous(tmp_path) -> None:
    storage, queue, engine = await _make_storage(tmp_path)
    try:
        key = _key()
        await storage.set_data(key, {"old": True})
        await storage.set_data(key, {"new": True})
        assert await storage.get_data(key) == {"new": True}
    finally:
        await queue.stop()
        await engine.dispose()


@pytest.mark.unit
async def test__update_data__merges_with_existing(tmp_path) -> None:
    storage, queue, engine = await _make_storage(tmp_path)
    try:
        key = _key()
        await storage.set_data(key, {"a": 1, "b": 2})
        merged = await storage.update_data(key, {"b": 20, "c": 3})
        assert merged == {"a": 1, "b": 20, "c": 3}
        assert await storage.get_data(key) == {"a": 1, "b": 20, "c": 3}
    finally:
        await queue.stop()
        await engine.dispose()


@pytest.mark.unit
async def test__update_data__no_existing__creates_row(tmp_path) -> None:
    storage, queue, engine = await _make_storage(tmp_path)
    try:
        key = _key(chat_id=777)
        merged = await storage.update_data(key, {"x": 42})
        assert merged == {"x": 42}
        assert await storage.get_data(key) == {"x": 42}
    finally:
        await queue.stop()
        await engine.dispose()
