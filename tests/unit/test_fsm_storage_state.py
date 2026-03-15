"""Tests for BotFSMStorage — state get/set operations."""

import pytest
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import StorageKey
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.db.fsm_storage import BotFSMStorage
from core.db.database import SQLiteWriterQueue, register_sqlite_pragmas
from core.db.models import Base


class _TestStates(StatesGroup):
    waiting_email = State()
    waiting_code = State()


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
async def test__set_state__string__roundtrip(tmp_path) -> None:
    storage, queue, engine = await _make_storage(tmp_path)
    try:
        key = _key()
        await storage.set_state(key, "some:state")
        assert await storage.get_state(key) == "some:state"
    finally:
        await queue.stop()
        await engine.dispose()


@pytest.mark.unit
async def test__get_state__no_row__returns_none(tmp_path) -> None:
    storage, queue, engine = await _make_storage(tmp_path)
    try:
        assert await storage.get_state(_key(chat_id=999)) is None
    finally:
        await queue.stop()
        await engine.dispose()


@pytest.mark.unit
async def test__set_state__none__clears_state(tmp_path) -> None:
    storage, queue, engine = await _make_storage(tmp_path)
    try:
        key = _key()
        await storage.set_state(key, "active")
        await storage.set_state(key, None)
        assert await storage.get_state(key) is None
    finally:
        await queue.stop()
        await engine.dispose()


@pytest.mark.unit
async def test__set_state__state_object__extracts_string(tmp_path) -> None:
    storage, queue, engine = await _make_storage(tmp_path)
    try:
        key = _key()
        await storage.set_state(key, _TestStates.waiting_email)
        assert await storage.get_state(key) == _TestStates.waiting_email.state
    finally:
        await queue.stop()
        await engine.dispose()


@pytest.mark.unit
async def test__set_state__overwrites_previous(tmp_path) -> None:
    storage, queue, engine = await _make_storage(tmp_path)
    try:
        key = _key()
        await storage.set_state(key, "first")
        await storage.set_state(key, "second")
        assert await storage.get_state(key) == "second"
    finally:
        await queue.stop()
        await engine.dispose()
