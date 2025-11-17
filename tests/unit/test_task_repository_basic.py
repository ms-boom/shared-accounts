"""Basic unit tests for bot/db/repositories/task_repository.py (SQLite compatible)."""

import pytest

from bot.db.repositories.task_repository import TaskRepository


@pytest.fixture
def task_repository(test_database):
    """Create TaskRepository instance for testing."""
    return TaskRepository(test_database)


@pytest.mark.unit
async def test_gets_pending_count_initially_zero(
    task_repository: TaskRepository,
) -> None:
    """Test that pending count is 0 initially."""
    count = await task_repository.get_pending_count()
    assert count == 0


@pytest.mark.skip(
    reason="Requires PostgreSQL JSONB type - SQLite doesn't support dict payload"
)
@pytest.mark.unit
async def test_creates_task(task_repository: TaskRepository) -> None:
    """Test creating a new task (requires PostgreSQL)."""
    pass


@pytest.mark.skip(
    reason="Requires FOR UPDATE SKIP LOCKED - PostgreSQL only feature"
)
@pytest.mark.unit
async def test_dequeue_pending_task(task_repository: TaskRepository) -> None:
    """Test dequeuing task (requires PostgreSQL)."""
    pass
