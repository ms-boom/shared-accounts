"""Simplified unit tests for bot/db/repositories/task_repository.py.

Note: Some tests are skipped because they require PostgreSQL-specific features:
- JSONB type for payload
- FOR UPDATE SKIP LOCKED for concurrent task processing

For full integration testing, use PostgreSQL database.
"""

import pytest

from bot.db.repositories.task_repository import TaskRepository
from tests.adapters import DatabasesAdapter


@pytest.mark.unit
class TestTaskRepositoryBasic:
    """Basic tests for TaskRepository (SQLite compatible)."""

    @pytest.fixture
    def task_repository(self, test_database_adapter: DatabasesAdapter):
        """Create TaskRepository instance for testing."""
        return TaskRepository(test_database_adapter)

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
@pytest.mark.skip(reason="Integration tests require PostgreSQL database")
class TestTaskRepositoryIntegration:
    """Integration tests for TaskRepository with PostgreSQL.

    These tests should be run against real PostgreSQL database.
    """

    @pytest.fixture
    def task_repository(self, test_database_adapter: DatabasesAdapter):
        """Create TaskRepository instance for testing."""
        return TaskRepository(test_database_adapter)
