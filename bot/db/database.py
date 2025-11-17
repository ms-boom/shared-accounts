"""Database connection and session management."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from databases import Database as DatabasesDatabase
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from bot.core.config import Settings
from bot.core.exceptions import DatabaseError
from bot.db.models import Base

logger = logging.getLogger(__name__)


class Database:
    """
    Database connection manager.

    Handles database initialization, connection lifecycle, and session management.
    """

    def __init__(self, settings: Settings):
        """
        Initialize database manager.

        Args:
            settings: Application settings containing database URL
        """
        self.settings = settings
        self.database_url = settings.DATABASE_URL
        self.engine: AsyncEngine | None = None
        self.database: DatabasesDatabase | None = None

    async def startup(self) -> None:
        """
        Initialize database connection.

        Creates engine and connects to database.
        Should be called on application startup.

        Raises:
            DatabaseError: If connection fails
        """
        try:
            # Create SQLAlchemy async engine
            self.engine = create_async_engine(
                self.database_url,
                echo=self.settings.DEBUG,
                future=True,
            )

            # Create databases instance for async queries
            self.database = DatabasesDatabase(self.database_url)
            await self.database.connect()

            logger.info(f"Database connected: {self.database_url}")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise DatabaseError(f"Database connection failed: {e}") from e

    async def shutdown(self) -> None:
        """
        Close database connection.

        Should be called on application shutdown.
        """
        if self.database:
            await self.database.disconnect()
            logger.info("Database disconnected")

        if self.engine:
            await self.engine.dispose()

    async def create_tables(self) -> None:
        """
        Create all database tables.

        WARNING: This drops existing tables! Use migrations in production.
        Only use for development/testing.
        """
        if not self.engine:
            raise DatabaseError(
                "Database engine not initialized. Call startup() first."
            )

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database tables created")

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[DatabasesDatabase]:
        """
        Create a database transaction context.

        Usage:
            async with database.transaction() as tx:
                await tx.execute(query)

        Yields:
            Database transaction object

        Raises:
            DatabaseError: If transaction fails
        """
        if not self.database:
            raise DatabaseError("Database not initialized. Call startup() first.")

        async with self.database.transaction():
            yield self.database

    def get_connection(self) -> DatabasesDatabase:
        """
        Get database connection.

        Returns:
            Database connection instance

        Raises:
            DatabaseError: If database not initialized
        """
        if not self.database:
            raise DatabaseError("Database not initialized. Call startup() first.")
        return self.database
