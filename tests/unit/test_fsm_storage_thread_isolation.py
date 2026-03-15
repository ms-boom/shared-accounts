"""Tests for BotFSMStorage — thread_id isolation (Topics support)."""

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
async def test__different_threads__independent_states(tmp_path) -> None:
    storage, queue, engine = await _make_storage(tmp_path)
    try:
        key_main = _key(thread_id=0)
        key_topic = _key(thread_id=100)

        await storage.set_state(key_main, "main_state")
        await storage.set_state(key_topic, "topic_state")

        assert await storage.get_state(key_main) == "main_state"
        assert await storage.get_state(key_topic) == "topic_state"
    finally:
        await queue.stop()
        await engine.dispose()


@pytest.mark.unit
async def test__different_threads__independent_data(tmp_path) -> None:
    storage, queue, engine = await _make_storage(tmp_path)
    try:
        key_main = _key(thread_id=0)
        key_topic = _key(thread_id=100)

        await storage.set_data(key_main, {"ctx": "main"})
        await storage.set_data(key_topic, {"ctx": "topic"})

        assert await storage.get_data(key_main) == {"ctx": "main"}
        assert await storage.get_data(key_topic) == {"ctx": "topic"}
    finally:
        await queue.stop()
        await engine.dispose()


@pytest.mark.unit
async def test__thread_id_none__treated_as_zero(tmp_path) -> None:
    storage, queue, engine = await _make_storage(tmp_path)
    try:
        key_none = _key(thread_id=None)
        key_zero = _key(thread_id=0)

        await storage.set_state(key_none, "via_none")
        assert await storage.get_state(key_zero) == "via_none"
    finally:
        await queue.stop()
        await engine.dispose()
