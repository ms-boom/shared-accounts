"""Database fixtures with scope-based transaction management.

This module implements database fixtures with:
- Session-scoped event loop (shared across all tests and fixtures)
- Session-scoped engine
- Session-scoped connection with Session.configure()
- Function-scoped transaction with automatic rollback
- Function-scoped savepoint with automatic recreation via event listener
- Allows fixtures to use commit() while maintaining test isolation
"""

import logging
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
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

from bot.core.config import Settings
from bot.db.models import Base

logger = logging.getLogger(__name__)

# Global test Session - будет переконфигурирован в фикстуре db_connection
# Pattern from intern-contest-cabinet for compatibility with db_savepoint event listener
Session = sa.orm.sessionmaker(
    expire_on_commit=False,
    class_=sa.ext.asyncio.AsyncSession,
)


@pytest.fixture(scope="session")
def test_settings(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    """Test configuration with PostgreSQL test database.

    This fixture provides configuration for the test database.
    Uses default postgres database to avoid conflicts.
    """
    # Create temp directories for test data
    temp_dir = tmp_path_factory.mktemp("test_data")

    settings = Settings(
        TELEGRAM_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/claude_bot_test",
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

    Note: Database migrations must be applied before running tests.
    Locally run: alembic upgrade head

    Pattern from intern-contest-cabinet with disabled statement caching to prevent
    event loop attachment issues when reusing connections from pool.
    """
    # Create PostgreSQL connection URL with asyncpg
    db_url = test_settings.DATABASE_URL

    # Disable statement caching to prevent event loop attachment issues
    # Pattern from intern-contest-cabinet project
    connect_args = {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    }

    # Pool settings from intern-contest-cabinet project
    # pool_recycle is critical to prevent stale connections and event loop issues
    engine = create_async_engine(
        db_url,
        echo=False,  # Set to True for SQL debugging
        pool_timeout=30,  # Seconds to wait for connection from pool
        pool_size=3,  # Number of connections to keep in pool
        pool_recycle=3600,  # Recycle connections after 1 hour
        pool_pre_ping=False,  # Matches intern-contest-cabinet settings
        max_overflow=2,  # Maximum overflow connections
        connect_args=connect_args,
    )

    # Configure global Session with engine first
    # Pattern from intern-contest-cabinet project - Session is configured twice:
    # 1. With engine here
    # 2. With connection in db_connection fixture
    Session.configure(bind=engine)

    yield engine

    # Cleanup - dispose engine
    await engine.dispose()


@pytest.fixture(scope="session")
async def db_connection(
    db_engine: AsyncEngine,
) -> AsyncGenerator[AsyncConnection, None]:
    """AsyncConnection for test database.

    Session-scoped connection reconfigured for test isolation.
    Uses pattern from intern-contest-cabinet with Session.configure().
    """
    async with db_engine.connect() as connection:
        # Reconfigure global Session to use connection instead of engine
        Session.configure(bind=connection)

        yield connection

        # Restore Session to use engine
        Session.configure(bind=db_engine)


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
            savepoint = db_connection.sync_connection.begin_nested()

    sa.event.listen(sa.orm.Session, "after_transaction_end", on_release_savepoint)
    yield
    sa.event.remove(sa.orm.Session, "after_transaction_end", on_release_savepoint)


@pytest.fixture(scope="function")
def db_sessionmaker(db_savepoint: None) -> async_sessionmaker[AsyncSession]:
    """Session factory for tests.

    Returns global test Session configured to use test connection.
    The connection is already in a transaction with savepoint (db_savepoint).
    Savepoints are automatically recreated after commits via event listener.
    """
    return Session  # type: ignore[return-value]


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
def test_database_adapter(db_session: AsyncSession):
    """databases.Database-compatible adapter using db_session.

    This fixture provides a databases.Database-compatible interface
    while using SQLAlchemy AsyncSession for better transaction isolation.

    Recommended for migrating tests from test_database to db_session
    without modifying repository code.
    """
    from tests.adapters import DatabasesAdapter

    return DatabasesAdapter(db_session)
