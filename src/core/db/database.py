"""Database configuration and session management for SQLite.

Pattern from statements/ project - global Session with proper configuration.

Usage in production code:
    async with db.Session() as session, session.begin():
        result = await session.execute(sa.select(Model).where(...))
        records = result.scalars().all()

Usage in repositories (session injection):
    class SomeRepository:
        def __init__(self, session: AsyncSession):
            self.session = session

        async def create(self, data):
            self.session.add(Model(**data))
            await self.session.flush()  # No commit in repository!
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import sqlalchemy as sa
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import Settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Global Session factory - configured once, reused everywhere
# Pattern from statements/db.py
Session = sa.orm.sessionmaker(
    expire_on_commit=False,  # Prevent attributes from being expired after commit
    class_=sa.ext.asyncio.AsyncSession,
)


def _apply_sqlite_pragmas(dbapi_connection: Any, connection_record: Any) -> None:
    """Apply required SQLite PRAGMAs to every new DBAPI connection.

    Called by SQLAlchemy's sync engine 'connect' event for each new connection.
    Must execute via cursor, not via SQLAlchemy ORM, because the event fires
    before the connection is handed to the pool.

    Args:
        dbapi_connection: Raw sqlite3.Connection from aiosqlite
        connection_record: SQLAlchemy connection record (unused)
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA cache_size=-64000")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def register_sqlite_pragmas(engine: AsyncEngine) -> None:
    """Register SQLite PRAGMA event listener on the given engine.

    Attaches `_apply_sqlite_pragmas` to the sync engine's 'connect' event
    so that every new DBAPI connection receives the required PRAGMAs.

    Called from `setup()` for SQLite engines and exported for use by test fixtures.

    Args:
        engine: AsyncEngine backed by SQLite (must be SQLite)
    """
    sa.event.listen(engine.sync_engine, "connect", _apply_sqlite_pragmas)


class SQLiteWriterQueue:
    """Serializes SQLite write operations through asyncio.Queue.

    Required for SQLite because concurrent writers cause 'database is locked'
    even with busy_timeout. The queue ensures writes execute one at a time
    within the same process.

    """

    def __init__(self, session_maker: async_sessionmaker[AsyncSession]) -> None:
        """
        Args:
            session_maker: SQLAlchemy async session factory
        """
        self._session_maker = session_maker
        self._queue: asyncio.Queue[
            tuple[asyncio.Future[Any], Callable[[AsyncSession], Awaitable[Any]]] | None
        ] = asyncio.Queue()
        self._stopped = False
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the background writer task.

        Must be called once before any execute() calls.
        Typically called from Database.startup().
        """
        self._task = asyncio.create_task(self._writer_loop())
        logger.info("SQLiteWriterQueue started")

    async def stop(self) -> None:
        """Graceful shutdown: drain pending writes, then stop.

        Sends sentinel to queue, waits up to 10 seconds for background
        task to finish. Cancels the task on timeout.
        """
        self._stopped = True
        await self._queue.put(None)  # sentinel to stop the loop
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=10.0)
            except TimeoutError:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
        logger.info("SQLiteWriterQueue stopped")

    async def execute(self, fn: Callable[[AsyncSession], Awaitable[T]]) -> T:
        """Submit a write operation to the serialized queue.

        Args:
            fn: Async callable that receives an AsyncSession and returns a result.
                The session is already within an open transaction when fn is called.
                fn must NOT call session.commit() — the queue handles commit.
                fn must NOT call session.close() — the queue handles cleanup.

        Returns:
            The return value of fn.

        Raises:
            RuntimeError: If called after stop().
            Any exception raised by fn — propagated via asyncio.Future.
        """
        if self._stopped:
            raise RuntimeError("SQLiteWriterQueue is stopped")

        loop = asyncio.get_running_loop()
        future: asyncio.Future[T] = loop.create_future()
        await self._queue.put((future, fn))
        return await future

    async def _writer_loop(self) -> None:
        """Background task: pull items from queue and execute them serially."""
        while True:
            item = await self._queue.get()
            if item is None:
                break
            future, fn = item
            try:
                async with self._session_maker() as session:
                    async with session.begin():
                        result = await fn(session)
                future.set_result(result)
            except Exception as exc:
                if not future.done():
                    future.set_exception(exc)


async def setup(settings: Settings) -> AsyncEngine:
    """Initialize SQLite database engine and configure global Session.

    This should be called once at application startup.
    Pattern from statements/db.py with simplified pool settings.

    Args:
        settings: Application settings

    Returns:
        Configured AsyncEngine
    """
    if (bind := Session.kw.get("bind")) is not None:
        logger.info("Database has already been initialized. Reusing existing engine.")
        # bind is AsyncEngine but mypy sees it as Any from dict.get()
        # We know it's AsyncEngine because we only put AsyncEngine there
        assert isinstance(bind, AsyncEngine), "Session bind must be AsyncEngine"
        return bind

    connect_args = {"check_same_thread": False}
    pool_size = 1
    max_overflow = 0
    logger.info("Using SQLite database with aiosqlite driver")

    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,  # Set to True for SQL debugging
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=30,  # Seconds to wait for connection from pool
        pool_recycle=3600,  # Recycle connections after 1 hour
        pool_pre_ping=False,  # Match statements settings
        connect_args=connect_args,
    )

    register_sqlite_pragmas(engine)

    # Configure global Session with engine
    Session.configure(bind=engine)
    logger.info(
        f"Database initialized with connection pool "
        f"(size={pool_size}, max_overflow={max_overflow})"
    )

    return engine


async def dispose():
    """Dispose database engine and cleanup resources."""
    if (bind := Session.kw.get("bind")) is not None:
        await bind.dispose()
        Session.configure(bind=None)
        logger.info("Database engine disposed")


class Database:
    """Database manager class for dependency injection.

    Provides access to SQLAlchemy Session factory and manages engine lifecycle.
    This class serves as a bridge between old DI code and new SQLAlchemy pattern.
    """

    def __init__(self, settings: Settings):
        """Initialize database manager.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self._engine: AsyncEngine | None = None
        self.writer_queue: SQLiteWriterQueue | None = None

    @property
    def session_maker(self) -> sa.orm.sessionmaker:
        """Get SQLAlchemy session factory.

        Returns:
            Global Session factory
        """
        return Session

    async def startup(self) -> None:
        """Initialize database engine and configure global Session.

        Creates and starts the writer queue to serialize concurrent write
        operations within the same process.
        """
        self._engine = await setup(self.settings)
        self.writer_queue = SQLiteWriterQueue(self.session_maker)  # type: ignore[arg-type]
        await self.writer_queue.start()

    async def shutdown(self) -> None:
        """Dispose database engine and cleanup resources.

        For SQLite, gracefully drains the writer queue before disposing the engine.
        """
        if self.writer_queue is not None:
            await self.writer_queue.stop()
            self.writer_queue = None
        await dispose()
        self._engine = None

    async def create_tables(self) -> None:
        """Create all database tables (development only)."""
        if not self._engine:
            raise RuntimeError("Database not initialized. Call startup() first.")

        from core.db.models import Base

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created")
