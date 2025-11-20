"""Database configuration and session management.

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

import logging

import sqlalchemy as sa
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from bot.core.config import Settings
from bot.db.dialect import CConnection
from bot.db.models import Base

logger = logging.getLogger(__name__)

# Global Session factory - configured once, reused everywhere
# Pattern from statements/db.py
Session = sa.orm.sessionmaker(
    expire_on_commit=False,  # Prevent attributes from being expired after commit
    class_=sa.ext.asyncio.AsyncSession,
)


async def setup(settings: Settings) -> AsyncEngine:
    """Initialize database engine and configure global Session.

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

    # Pattern from statements - use CConnection and disable statement caching
    connect_args = {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "connection_class": CConnection,
    }

    # Create engine with connection pooling
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,  # Set to True for SQL debugging
        pool_size=5,  # Number of connections to keep in pool
        max_overflow=10,  # Maximum overflow connections
        pool_timeout=30,  # Seconds to wait for connection from pool
        pool_recycle=3600,  # Recycle connections after 1 hour
        pool_pre_ping=False,  # Match statements settings
        connect_args=connect_args,
    )

    # Configure global Session with engine
    Session.configure(bind=engine)
    logger.info("Database initialized with connection pool (size=5, max_overflow=10)")

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

    @property
    def session_maker(self) -> sa.orm.sessionmaker:
        """Get SQLAlchemy session factory.

        Returns:
            Global Session factory
        """
        return Session

    async def startup(self) -> None:
        """Initialize database engine and configure global Session."""
        self._engine = await setup(self.settings)

    async def shutdown(self) -> None:
        """Dispose database engine and cleanup resources."""
        await dispose()
        self._engine = None

    async def create_tables(self) -> None:
        """Create all database tables (development only)."""
        if not self._engine:
            raise RuntimeError("Database not initialized. Call startup() first.")

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created")
