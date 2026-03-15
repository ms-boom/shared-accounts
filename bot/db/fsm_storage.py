"""Dialect-aware FSM storage for aiogram."""

from collections.abc import Mapping
from typing import Any, cast

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StateType, StorageKey
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.database import SQLiteWriterQueue
from bot.db.models import FSMState
from bot.db.upsert import build_upsert

_CONFLICT_COLUMNS = ["chat_id", "user_id", "thread_id"]


class BotFSMStorage(BaseStorage):
    """Dialect-aware FSM storage for aiogram.

    Supports both PostgreSQL and SQLite backends. For SQLite, routes write
    operations through SQLiteWriterQueue to prevent concurrent write conflicts.

    Attributes:
        session_maker: SQLAlchemy async session factory
        writer_queue: Optional queue for serializing SQLite writes
    """

    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        writer_queue: SQLiteWriterQueue | None = None,
    ) -> None:
        """
        Initialize FSM storage.

        Args:
            session_maker: SQLAlchemy async session factory
            writer_queue: Writer queue for SQLite serialization. None for PostgreSQL.
        """
        self.session_maker = session_maker
        self.writer_queue = writer_queue

    # --- Private write helpers (called with an already-open session) ---

    async def _write_state(
        self, session: AsyncSession, key: StorageKey, state_name: str | None
    ) -> None:
        """Execute upsert for state column only."""
        stmt = build_upsert(
            FSMState,
            values={
                "chat_id": key.chat_id,
                "user_id": key.user_id,
                "thread_id": key.thread_id or 0,
                "state": state_name,
            },
            conflict_columns=_CONFLICT_COLUMNS,
            update_columns={"state": state_name},
            session=session,
        )
        await session.execute(stmt)

    async def _write_data(
        self, session: AsyncSession, key: StorageKey, data_dict: dict[str, Any]
    ) -> None:
        """Execute upsert for data column only."""
        stmt = build_upsert(
            FSMState,
            values={
                "chat_id": key.chat_id,
                "user_id": key.user_id,
                "thread_id": key.thread_id or 0,
                "data": data_dict,
            },
            conflict_columns=_CONFLICT_COLUMNS,
            update_columns={"data": data_dict},
            session=session,
        )
        await session.execute(stmt)

    # --- Public write methods ---

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        """
        Set state for user in chat.

        Args:
            key: Storage key (bot_id, chat_id, user_id, thread_id)
            state: State to set (None to clear state)
        """
        state_name = state.state if isinstance(state, State) else state

        if self.writer_queue is not None:
            await self.writer_queue.execute(
                lambda s: self._write_state(s, key, state_name)
            )
        else:
            async with self.session_maker() as session:
                await self._write_state(session, key, state_name)
                await session.commit()

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        """
        Set data for user in chat.

        Args:
            key: Storage key (bot_id, chat_id, user_id, thread_id)
            data: Data to store
        """
        data_dict = dict(data)

        if self.writer_queue is not None:
            await self.writer_queue.execute(
                lambda s: self._write_data(s, key, data_dict)
            )
        else:
            async with self.session_maker() as session:
                await self._write_data(session, key, data_dict)
                await session.commit()

    async def update_data(
        self, key: StorageKey, data: Mapping[str, Any]
    ) -> dict[str, Any]:
        """
        Update data for user in chat (merge with existing).

        Args:
            key: Storage key (bot_id, chat_id, user_id, thread_id)
            data: Data to merge

        Returns:
            Updated data
        """
        async with self.session_maker() as session:
            select_stmt = select(FSMState.data).where(
                FSMState.chat_id == key.chat_id,
                FSMState.user_id == key.user_id,
                FSMState.thread_id == (key.thread_id or 0),
            )
            result = await session.execute(select_stmt)
            existing_data: dict[str, Any] = result.scalar_one_or_none() or {}

        merged_data = {**existing_data, **data}

        if self.writer_queue is not None:
            await self.writer_queue.execute(
                lambda s: self._write_data(s, key, merged_data)
            )
        else:
            async with self.session_maker() as session:
                await self._write_data(session, key, merged_data)
                await session.commit()

        return merged_data

    # --- Read methods (bypass queue — WAL allows concurrent reads) ---

    async def get_state(self, key: StorageKey) -> str | None:
        """
        Get state for user in chat.

        Args:
            key: Storage key (bot_id, chat_id, user_id, thread_id)

        Returns:
            Current state or None if no state set
        """
        async with self.session_maker() as session:
            stmt = select(FSMState.state).where(
                FSMState.chat_id == key.chat_id,
                FSMState.user_id == key.user_id,
                FSMState.thread_id == (key.thread_id or 0),
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            return cast(str | None, row)

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        """
        Get data for user in chat.

        Args:
            key: Storage key (bot_id, chat_id, user_id, thread_id)

        Returns:
            Stored data or empty dict if no data
        """
        async with self.session_maker() as session:
            stmt = select(FSMState.data).where(
                FSMState.chat_id == key.chat_id,
                FSMState.user_id == key.user_id,
                FSMState.thread_id == (key.thread_id or 0),
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            return row if row is not None else {}

    async def close(self) -> None:
        """Close storage (cleanup resources)."""
        pass
