"""SQLite FSM storage for aiogram."""

from collections.abc import Mapping
from typing import Any

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StateType, StorageKey
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.database import Database
from core.db.models import FSMState

_CONFLICT_COLUMNS = ["chat_id", "user_id", "thread_id"]


class BotFSMStorage(BaseStorage):
    """SQLite FSM storage for aiogram.

    Routes write operations through Database.write() to prevent concurrent
    SQLite write conflicts, and reads directly via Database.read().

    Attributes:
        db: Database instance providing read/write access
    """

    def __init__(self, db: Database) -> None:
        """
        Initialize FSM storage.

        Args:
            db: Database instance (must be started via startup() before use).
        """
        self.db = db

    # --- Private write helpers (called with an already-open session) ---

    async def _write_state(
        self, session: AsyncSession, key: StorageKey, state_name: str | None
    ) -> None:
        """Execute upsert for state column only."""
        stmt = (
            sqlite_insert(FSMState)
            .values(
                chat_id=key.chat_id,
                user_id=key.user_id,
                thread_id=key.thread_id or 0,
                state=state_name,
            )
            .on_conflict_do_update(
                index_elements=_CONFLICT_COLUMNS,
                set_={"state": state_name},
            )
        )
        await session.execute(stmt)

    async def _write_data(
        self, session: AsyncSession, key: StorageKey, data_dict: dict[str, Any]
    ) -> None:
        """Execute upsert for data column only."""
        stmt = (
            sqlite_insert(FSMState)
            .values(
                chat_id=key.chat_id,
                user_id=key.user_id,
                thread_id=key.thread_id or 0,
                data=data_dict,
            )
            .on_conflict_do_update(
                index_elements=_CONFLICT_COLUMNS,
                set_={"data": data_dict},
            )
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

        await self.db.write(lambda s: self._write_state(s, key, state_name))

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        """
        Set data for user in chat.

        Args:
            key: Storage key (bot_id, chat_id, user_id, thread_id)
            data: Data to store
        """
        data_dict = dict(data)

        await self.db.write(lambda s: self._write_data(s, key, data_dict))

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
        async with self.db.read() as session:
            select_stmt = select(FSMState.data).where(
                FSMState.chat_id == key.chat_id,
                FSMState.user_id == key.user_id,
                FSMState.thread_id == (key.thread_id or 0),
            )
            result = await session.execute(select_stmt)
            existing_data: dict[str, Any] = result.scalar_one_or_none() or {}

        merged_data = {**existing_data, **data}

        await self.db.write(lambda s: self._write_data(s, key, merged_data))

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
        async with self.db.read() as session:
            stmt = select(FSMState.state).where(
                FSMState.chat_id == key.chat_id,
                FSMState.user_id == key.user_id,
                FSMState.thread_id == (key.thread_id or 0),
            )
            result = await session.execute(stmt)
            state: str | None = result.scalar_one_or_none()
            return state

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        """
        Get data for user in chat.

        Args:
            key: Storage key (bot_id, chat_id, user_id, thread_id)

        Returns:
            Stored data or empty dict if no data
        """
        async with self.db.read() as session:
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
