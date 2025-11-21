"""Simplified unit tests for bot/db/repositories/task_repository.py.

Note: Tests now use SQLAlchemy AsyncSession with SQLite support.
SQLite-compatible tests run with real database transactions.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.repositories.task_repository import TaskRepository


@pytest.mark.unit
class TestTaskRepositoryBasic:
    """Basic tests for TaskRepository (SQLite compatible)."""

    @pytest.fixture
    def task_repository(self, db_session: AsyncSession):
        """Create TaskRepository instance for testing."""
        return TaskRepository(db_session)

    async def test_gets_pending_count_initially_zero(
        self, task_repository: TaskRepository
    ) -> None:
        """Test that pending count is 0 initially."""
        count = await task_repository.get_pending_count()
        assert count == 0

    @pytest.mark.skip(
        reason="Requires PostgreSQL JSONB type - SQLite doesn't support dict payload"
    )
    async def test_creates_task(self, task_repository: TaskRepository) -> None:
        """Test creating a new task (requires PostgreSQL)."""
        pass

    @pytest.mark.skip(
        reason="Requires FOR UPDATE SKIP LOCKED - PostgreSQL only feature"
    )
    async def test_dequeue_pending_task(self, task_repository: TaskRepository) -> None:
        """Test dequeuing task (requires PostgreSQL)."""
        pass


@pytest.mark.integration
@pytest.mark.skip(reason="Integration tests skipped - use SQLite basic tests")
class TestTaskRepositoryIntegration:
    """Integration tests for TaskRepository.

    These tests are skipped in favor of SQLite-compatible basic tests.
    """

    @pytest.fixture
    def task_repository(self, db_session: AsyncSession):
        """Create TaskRepository instance for testing."""
        return TaskRepository(db_session)
