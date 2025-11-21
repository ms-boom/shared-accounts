"""Database fixtures with scope-based transaction management.

This module implements database fixtures with:
- Session-scoped event loop (shared across all tests and fixtures)
- Session-scoped engine
- Session-scoped connection with Session.configure()
- Function-scoped transaction with automatic rollback
- Function-scoped savepoint with automatic recreation via event listener
- Allows fixtures to use commit() while maintaining test isolation
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from tests.adapters import DatabasesAdapter
import sqlalchemy as sa
import sqlalchemy.event
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
from alembic.command import upgrade
from alembic.config import Config
from databases import Database
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import bot.db.database as db  # Import production database module
from bot.core.config import Settings

logger = logging.getLogger(__name__)

# Use global Session from production code
# Pattern from statements/ - no need to create test-specific Session
# Production Session will be reconfigured in db_connection fixture


@pytest.fixture(scope="session")
def test_settings(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    """Test configuration with SQLite test database.

    This fixture provides configuration for the test database.
    Uses SQLite in-memory or temp file for isolated testing.

    DATABASE_URL can be overridden via environment variable for CI/CD.
    """
    import os

    # Create temp directories for test data
    temp_dir = tmp_path_factory.mktemp("test_data")

    # Use environment variable if set (for CI/CD), otherwise use SQLite
    database_url = os.getenv(
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{temp_dir}/test.db",
    )

    settings = Settings(
        TELEGRAM_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        DATABASE_URL=database_url,
        LOG_LEVEL="DEBUG",
        DEBUG=True,
        DATA_DIR=temp_dir / "data",
        SESSION_DIR=temp_dir / "sessions",
        LOG_DIR=temp_dir / "logs",
        ERROR_DIR=temp_dir / "errors",
        PERMISSION_CACHE_TTL=1,  # Short TTL for testing
    )

    # Ensure directories exist
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.SESSION_DIR.mkdir(parents=True, exist_ok=True)
    settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
    settings.ERROR_DIR.mkdir(parents=True, exist_ok=True)

    return settings


@pytest.fixture(scope="session")
def migrations(test_settings: Settings) -> None:
    """Run Alembic migrations for test database.

    NOTE: This fixture is NOT USED by default to avoid running migrations twice.
    Migrations are applied in CI before_script or manually before running tests.
    For local testing, run: alembic upgrade head

    This fixture is kept for backwards compatibility and emergency use cases.
    To enable it, add 'migrations' parameter to db_engine fixture.
    """
    # Disable Alembic logger
    logging.getLogger("alembic").setLevel(logging.CRITICAL)

    # Create Alembic config
    alembic_cfg = Config("alembic.ini")

    # Set database URL for test database
    db_url = test_settings.DATABASE_URL.replace("+asyncpg", "")
    db_url = db_url.replace("postgresql", "postgresql+psycopg2")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # Run migrations
    upgrade(alembic_cfg, "head")


@pytest.fixture(scope="session")
async def db_engine(test_settings: Settings) -> AsyncGenerator[AsyncEngine, None]:
    """AsyncEngine for test database.

    Session-scoped engine shared across all tests.
    Supports both PostgreSQL and SQLite based on DATABASE_URL.

    Note: Database migrations must be applied before running tests.
    Locally run: alembic upgrade head

    Pattern from statements/tests/fixtures/db.py
    """
    # Detect database type from URL
    db_url = test_settings.DATABASE_URL.lower()
    is_sqlite = db_url.startswith("sqlite")
    is_postgres = "postgres" in db_url

    # Configure connect_args based on database type
    connect_args: dict = {}

    if is_postgres:
        # PostgreSQL-specific configuration
        from bot.db.dialect import CConnection

        connect_args = {
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            "connection_class": CConnection,
        }
    elif is_sqlite:
        # SQLite-specific configuration
        connect_args = {
            "check_same_thread": False,  # Allow usage across threads
        }

    # Create engine with appropriate pool settings
    pool_size = 1 if is_sqlite else 5
    max_overflow = 0 if is_sqlite else 10

    engine = create_async_engine(
        test_settings.DATABASE_URL,
        echo=False,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=30,
        pool_recycle=3600,
        pool_pre_ping=False,
        connect_args=connect_args,
    )

    # Create tables for SQLite (in-memory DB needs schema)
    if is_sqlite:
        from bot.db.models import Base

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup - dispose engine
    await engine.dispose()


@pytest.fixture(scope="session")
async def db_connection(
    db_engine: AsyncEngine,
) -> AsyncGenerator[AsyncConnection, None]:
    """AsyncConnection for test database.

    Session-scoped connection reconfigured for test isolation.
    Pattern from statements/tests/fixtures/db.py
    """
    async with db_engine.connect() as connection:
        # Reconfigure global Session to use connection instead of engine
        # This is critical for test isolation via transactions
        db.Session.configure(bind=connection)

        yield connection

        # Restore Session to use engine after tests
        db.Session.configure(bind=db_engine)


@pytest.fixture(scope="function")
async def db_transaction(db_connection: AsyncConnection) -> AsyncGenerator[None, None]:
    """Transaction with automatic rollback after test.

    Function-scoped transaction that ensures test isolation.
    All database changes are rolled back after each test.
    """
    transaction: sa.ext.asyncio.AsyncTransaction = await db_connection.begin()
    yield
    await transaction.rollback()


@pytest.fixture(scope="function")
async def db_savepoint(
    db_transaction: None, db_connection: AsyncConnection
) -> AsyncGenerator[None, None]:
    """Savepoint with automatic recreation after commit.

    This fixture creates a SAVEPOINT and registers an event listener
    that automatically recreates the savepoint after each transaction end.
    This allows fixture code to use commit() while maintaining test isolation.

    Pattern from intern-contest-cabinet project for compatibility with fixture commits.
    Event listener is called synchronously, so it uses sync_connection.
    """
    savepoint: (
        sa.ext.asyncio.AsyncTransaction | sa.engine.NestedTransaction
    ) = await db_connection.begin_nested()

    def on_release_savepoint(session, tx):
        nonlocal savepoint
        if not savepoint.is_active:
            # Event listener is called synchronously, use sync_connection
            if db_connection.sync_connection is None:
                raise RuntimeError("sync_connection is None")
            savepoint = db_connection.sync_connection.begin_nested()

    sa.event.listen(sa.orm.Session, "after_transaction_end", on_release_savepoint)
    yield
    sa.event.remove(sa.orm.Session, "after_transaction_end", on_release_savepoint)


@pytest.fixture(scope="function")
def db_sessionmaker(db_savepoint: None) -> async_sessionmaker[AsyncSession]:
    """Session factory for tests.

    Returns global Session configured to use test connection.
    The connection is already in a transaction with savepoint (db_savepoint).
    Savepoints are automatically recreated after commits via event listener.

    Pattern from statements/ - use production Session
    """
    return db.Session  # type: ignore[return-value]


@pytest.fixture(scope="function")
async def db_session(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """AsyncSession for tests with automatic cleanup.

    Provides a database session for direct database operations in tests.
    Changes are automatically rolled back via transaction fixture.
    """
    async with db_sessionmaker() as session:
        yield session


@pytest.fixture
async def test_database(test_settings: Settings) -> AsyncGenerator[Database, None]:
    """Legacy databases.Database fixture for backward compatibility.

    This fixture provides a databases.Database connection for tests that use it.
    New code should prefer using db_session fixture with SQLAlchemy.

    Note: This creates a NEW connection outside of the transaction context,
    so it won't see uncommitted changes from db_session. Use with caution.
    """
    database = Database(test_settings.DATABASE_URL)
    await database.connect()

    yield database

    await database.disconnect()


@pytest.fixture
async def test_database_adapter(
    db_session: AsyncSession,
) -> AsyncGenerator[DatabasesAdapter, None]:
    """databases.Database-compatible adapter using db_session.

    This fixture provides a databases.Database-compatible interface
    while using SQLAlchemy AsyncSession for better transaction isolation.

    Recommended for migrating tests from test_database to db_session
    without modifying repository code.
    """
    from tests.adapters import DatabasesAdapter

    yield DatabasesAdapter(db_session)
