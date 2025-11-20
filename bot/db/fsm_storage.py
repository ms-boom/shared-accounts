"""PostgreSQL-based FSM storage for aiogram."""

from collections.abc import Mapping
from typing import Any, cast

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StateType, StorageKey
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import FSMState


class PostgreSQLStorage(BaseStorage):
    """
    PostgreSQL-based FSM storage implementation for aiogram.

    Provides persistent storage for conversation states using PostgreSQL.
    Thread-safe and supports concurrent access from multiple bot instances.

    Attributes:
        session_maker: SQLAlchemy async session maker
    """

    def __init__(self, session_maker: async_sessionmaker[AsyncSession]) -> None:
        """
        Initialize PostgreSQL storage.

        Args:
            session_maker: SQLAlchemy async session maker
        """
        self.session_maker = session_maker

    async def set_state(
        self,
        key: StorageKey,
        state: StateType = None,
    ) -> None:
        """
        Set state for user in chat.

        Args:
            key: Storage key (bot_id, chat_id, user_id, thread_id)
            state: State to set (None to clear state)
        """
        state_name = state.state if isinstance(state, State) else state

        async with self.session_maker() as session:
            stmt = (
                insert(FSMState)
                .values(
                    chat_id=key.chat_id,
                    user_id=key.user_id,
                    thread_id=key.thread_id or 0,
                    state=state_name,
                )
                .on_conflict_do_update(
                    index_elements=["chat_id", "user_id", "thread_id"],
                    set_={"state": state_name},
                )
            )
            await session.execute(stmt)
            await session.commit()

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
            # SQLAlchemy returns Any from scalar_one_or_none, but we know it's str | None
            return cast(str | None, row)

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        """
        Set data for user in chat.

        Args:
            key: Storage key (bot_id, chat_id, user_id, thread_id)
            data: Data to store
        """
        data_dict = dict(data)  # Convert Mapping to dict for JSONB storage
        async with self.session_maker() as session:
            stmt = (
                insert(FSMState)
                .values(
                    chat_id=key.chat_id,
                    user_id=key.user_id,
                    thread_id=key.thread_id or 0,
                    data=data_dict,
                )
                .on_conflict_do_update(
                    index_elements=["chat_id", "user_id", "thread_id"],
                    set_={"data": data_dict},
                )
            )
            await session.execute(stmt)
            await session.commit()

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
            # Get existing data
            select_stmt = select(FSMState.data).where(
                FSMState.chat_id == key.chat_id,
                FSMState.user_id == key.user_id,
                FSMState.thread_id == (key.thread_id or 0),
            )
            result = await session.execute(select_stmt)
            existing_data = result.scalar_one_or_none() or {}

            # Merge with new data
            updated_data = {**existing_data, **data}

            # Update in database
            insert_stmt = (
                insert(FSMState)
                .values(
                    chat_id=key.chat_id,
                    user_id=key.user_id,
                    thread_id=key.thread_id or 0,
                    data=updated_data,
                )
                .on_conflict_do_update(
                    index_elements=["chat_id", "user_id", "thread_id"],
                    set_={"data": updated_data},
                )
            )
            await session.execute(insert_stmt)
            await session.commit()

            return updated_data

    async def close(self) -> None:
        """Close storage (cleanup resources)."""
        # Session maker doesn't need explicit closing
        pass
