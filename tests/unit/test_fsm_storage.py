"""Tests for BotFSMStorage — SQLite FSM storage for aiogram.

Test List:
- [x] set_state / get_state: round-trip for a simple state
- [x] get_state: returns None when no state exists
- [x] set_state: clears state when None passed
- [x] set_state: accepts State object (not just string)
- [x] set_data / get_data: round-trip for dict data
- [x] get_data: returns empty dict when no data exists
- [x] update_data: merges with existing data
- [x] update_data: creates new row when no data exists
- [x] thread_id isolation: different threads have independent states
- [x] thread_id None treated as 0
- [x] upsert: set_state overwrites previous state
- [x] upsert: set_data overwrites previous data
"""

import pytest
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import StorageKey
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.db.fsm_storage import BotFSMStorage
from core.db.database import SQLiteWriterQueue, register_sqlite_pragmas
from core.db.models import Base


class _TestStates(StatesGroup):
    """FSM states for testing."""

    waiting_email = State()
    waiting_code = State()


def _key(
    chat_id: int = 100, user_id: int = 200, thread_id: int | None = None
) -> StorageKey:
    """Create a StorageKey with sensible defaults."""
    return StorageKey(bot_id=1, chat_id=chat_id, user_id=user_id, thread_id=thread_id)


async def _make_storage(tmp_path):
    """Create standalone Database + BotFSMStorage for a single test."""
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

    # Build a minimal Database-like object that BotFSMStorage needs
    class _FakeDatabase:
        async def write(self, fn):
            return await writer_queue.execute(fn)

        def read(self):
            return session_maker()

    storage = BotFSMStorage(_FakeDatabase())
    return storage, writer_queue, engine


@pytest.mark.unit
class TestFSMStorageState:
    """Tests for state get/set operations."""

    async def test__set_state__string__roundtrip(self, tmp_path) -> None:
        """set_state with a string, get_state returns the same string."""
        storage, queue, engine = await _make_storage(tmp_path)
        try:
            key = _key()
            await storage.set_state(key, "some:state")

            result = await storage.get_state(key)
            assert result == "some:state"
        finally:
            await queue.stop()
            await engine.dispose()

    async def test__get_state__no_row__returns_none(self, tmp_path) -> None:
        """get_state on missing key returns None."""
        storage, queue, engine = await _make_storage(tmp_path)
        try:
            result = await storage.get_state(_key(chat_id=999))
            assert result is None
        finally:
            await queue.stop()
            await engine.dispose()

    async def test__set_state__none__clears_state(self, tmp_path) -> None:
        """set_state(None) clears a previously stored state."""
        storage, queue, engine = await _make_storage(tmp_path)
        try:
            key = _key()
            await storage.set_state(key, "active")
            await storage.set_state(key, None)

            result = await storage.get_state(key)
            assert result is None
        finally:
            await queue.stop()
            await engine.dispose()

    async def test__set_state__state_object__extracts_string(self, tmp_path) -> None:
        """set_state accepts aiogram State objects."""
        storage, queue, engine = await _make_storage(tmp_path)
        try:
            key = _key()
            await storage.set_state(key, _TestStates.waiting_email)

            result = await storage.get_state(key)
            assert result == _TestStates.waiting_email.state
        finally:
            await queue.stop()
            await engine.dispose()

    async def test__set_state__overwrites_previous(self, tmp_path) -> None:
        """Second set_state overwrites the first (upsert)."""
        storage, queue, engine = await _make_storage(tmp_path)
        try:
            key = _key()
            await storage.set_state(key, "first")
            await storage.set_state(key, "second")

            result = await storage.get_state(key)
            assert result == "second"
        finally:
            await queue.stop()
            await engine.dispose()


@pytest.mark.unit
class TestFSMStorageData:
    """Tests for data get/set/update operations."""

    async def test__set_data__roundtrip(self, tmp_path) -> None:
        """set_data stores dict, get_data returns same dict."""
        storage, queue, engine = await _make_storage(tmp_path)
        try:
            key = _key()
            await storage.set_data(key, {"email": "test@example.com", "step": 2})

            result = await storage.get_data(key)
            assert result == {"email": "test@example.com", "step": 2}
        finally:
            await queue.stop()
            await engine.dispose()

    async def test__get_data__no_row__returns_empty_dict(self, tmp_path) -> None:
        """get_data on missing key returns {}."""
        storage, queue, engine = await _make_storage(tmp_path)
        try:
            result = await storage.get_data(_key(chat_id=999))
            assert result == {}
        finally:
            await queue.stop()
            await engine.dispose()

    async def test__set_data__overwrites_previous(self, tmp_path) -> None:
        """Second set_data replaces the first (upsert)."""
        storage, queue, engine = await _make_storage(tmp_path)
        try:
            key = _key()
            await storage.set_data(key, {"old": True})
            await storage.set_data(key, {"new": True})

            result = await storage.get_data(key)
            assert result == {"new": True}
        finally:
            await queue.stop()
            await engine.dispose()

    async def test__update_data__merges_with_existing(self, tmp_path) -> None:
        """update_data merges new keys into existing data."""
        storage, queue, engine = await _make_storage(tmp_path)
        try:
            key = _key()
            await storage.set_data(key, {"a": 1, "b": 2})

            merged = await storage.update_data(key, {"b": 20, "c": 3})

            assert merged == {"a": 1, "b": 20, "c": 3}

            result = await storage.get_data(key)
            assert result == {"a": 1, "b": 20, "c": 3}
        finally:
            await queue.stop()
            await engine.dispose()

    async def test__update_data__no_existing__creates_row(self, tmp_path) -> None:
        """update_data on missing key creates a new row."""
        storage, queue, engine = await _make_storage(tmp_path)
        try:
            key = _key(chat_id=777)

            merged = await storage.update_data(key, {"x": 42})

            assert merged == {"x": 42}

            result = await storage.get_data(key)
            assert result == {"x": 42}
        finally:
            await queue.stop()
            await engine.dispose()


@pytest.mark.unit
class TestFSMStorageThreadIsolation:
    """Tests for thread_id isolation (Topics support)."""

    async def test__different_threads__independent_states(self, tmp_path) -> None:
        """State in thread 0 is independent from state in thread 100."""
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

    async def test__different_threads__independent_data(self, tmp_path) -> None:
        """Data in thread 0 is independent from data in thread 100."""
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

    async def test__thread_id_none__treated_as_zero(self, tmp_path) -> None:
        """thread_id=None in StorageKey is stored as 0."""
        storage, queue, engine = await _make_storage(tmp_path)
        try:
            key_none = _key(thread_id=None)
            key_zero = _key(thread_id=0)

            await storage.set_state(key_none, "via_none")

            result = await storage.get_state(key_zero)
            assert result == "via_none"
        finally:
            await queue.stop()
            await engine.dispose()
