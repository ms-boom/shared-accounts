"""Unit tests for TaskRepository optimistic locking functionality."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.repositories.task_repository import TaskRepository


@pytest.mark.unit
class TestTaskRepositoryOptimisticLocking:
    """Tests for TaskRepository optimistic locking with version field."""

    @pytest.fixture
    def task_repo(self, db_session: AsyncSession):
        """Create TaskRepository instance for testing."""
        return TaskRepository(db_session)

    async def test_update_status_requires_version_parameter(
        self, task_repo: TaskRepository
    ) -> None:
        """Test that update_status requires expected_version parameter."""
        import inspect

        sig = inspect.signature(task_repo.update_status)

        # Verify expected_version parameter exists
        assert "expected_version" in sig.parameters
        assert "task_id" in sig.parameters
        assert "status" in sig.parameters
        assert "result" in sig.parameters

        # expected_version should be required (no default)
        assert sig.parameters["expected_version"].default == inspect.Parameter.empty

    async def test_recover_stuck_tasks_method_exists(
        self, task_repo: TaskRepository
    ) -> None:
        """Test that recover_stuck_tasks method exists."""
        assert hasattr(task_repo, "recover_stuck_tasks")

        import inspect

        sig = inspect.signature(task_repo.recover_stuck_tasks)

        # Verify stuck_timeout_minutes parameter with default value
        assert "stuck_timeout_minutes" in sig.parameters
        assert sig.parameters["stuck_timeout_minutes"].default == 5
