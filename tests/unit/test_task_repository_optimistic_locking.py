"""Unit tests for TaskRepository optimistic locking functionality."""

import pytest

from bot.db.repositories.task_repository import TaskRepository
from tests.adapters import DatabasesAdapter


@pytest.mark.unit
class TestTaskRepositoryOptimisticLocking:
    """Tests for TaskRepository optimistic locking with version field."""

    @pytest.fixture
    def task_repo(self, test_database_adapter: DatabasesAdapter):
        """Create TaskRepository instance for testing."""
        return TaskRepository(test_database_adapter)

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


@pytest.mark.integration
@pytest.mark.skip(reason="Integration tests require PostgreSQL database")
class TestTaskRepositoryOptimisticLockingIntegration:
    """Integration tests for optimistic locking with PostgreSQL.

    These tests require PostgreSQL database to verify actual locking behavior.
    """

    @pytest.fixture
    def task_repo(self, test_database_adapter: DatabasesAdapter):
        """Create TaskRepository instance for testing."""
        return TaskRepository(test_database_adapter)

    async def test_create_task_includes_version(
        self, task_repo: TaskRepository
    ) -> None:
        """Test that created task includes version field with initial value 1."""
        task = await task_repo.create(
            chat_id=123456,
            user_id=789,
            task_type="init_session",
            payload={"email": "test@example.com"},
        )

        assert "version" in task
        assert task["version"] == 1

    async def test_update_status_increments_version(
        self, task_repo: TaskRepository
    ) -> None:
        """Test that update_status increments version."""
        # Create task
        task = await task_repo.create(
            chat_id=123456,
            user_id=789,
            task_type="init_session",
            payload={"email": "test@example.com"},
        )

        initial_version = task["version"]

        # Update status with correct version
        updated = await task_repo.update_status(
            task_id=task["id"],
            status="done",
            expected_version=initial_version,
            result="Success",
        )

        assert updated is not None
        assert updated["version"] == initial_version + 1
        assert updated["status"] == "done"

    async def test_update_status_fails_with_wrong_version(
        self, task_repo: TaskRepository
    ) -> None:
        """Test that update_status fails when version doesn't match."""
        # Create task
        task = await task_repo.create(
            chat_id=123456,
            user_id=789,
            task_type="init_session",
            payload={"email": "test@example.com"},
        )

        # Try to update with wrong version
        wrong_version = 999
        updated = await task_repo.update_status(
            task_id=task["id"],
            status="done",
            expected_version=wrong_version,
            result="Success",
        )

        # Should return None due to version mismatch
        assert updated is None

        # Task status should remain unchanged
        task_after = await task_repo.get_by_id(task["id"])
        assert task_after["status"] == "pending"
        assert task_after["version"] == 1

    async def test_dequeue_increments_version(
        self, task_repo: TaskRepository
    ) -> None:
        """Test that dequeue_pending_task increments version."""
        # Create pending task
        await task_repo.create(
            chat_id=123456,
            user_id=789,
            task_type="get_code",
            payload={"url": "https://claude.ai/auth"},
        )

        # Dequeue task
        dequeued = await task_repo.dequeue_pending_task()

        assert dequeued is not None
        assert dequeued["status"] == "processing"
        assert dequeued["version"] == 2  # Incremented from 1 to 2

    async def test_recover_stuck_tasks_resets_to_pending(
        self, task_repo: TaskRepository
    ) -> None:
        """Test that recover_stuck_tasks resets stuck tasks to pending."""
        # Create task and manually mark as processing
        task = await task_repo.create(
            chat_id=123456,
            user_id=789,
            task_type="get_code",
            payload={"url": "https://claude.ai/auth"},
        )

        # Manually set to processing with old timestamp
        # (In real scenario this would be done via dequeue)
        import datetime

        old_time = datetime.datetime.utcnow() - datetime.timedelta(minutes=10)

        # Simulate stuck task by updating directly in DB
        from databases import Database

        db: Database = test_database_adapter
        await db.execute(
            """
            UPDATE tasks
            SET status = 'processing',
                updated_at = :updated_at
            WHERE id = :task_id
            """,
            {"task_id": str(task["id"]), "updated_at": old_time},
        )

        # Recover stuck tasks (timeout = 5 minutes)
        recovered_count = await task_repo.recover_stuck_tasks(
            stuck_timeout_minutes=5
        )

        assert recovered_count == 1

        # Check task is back to pending
        recovered_task = await task_repo.get_by_id(task["id"])
        assert recovered_task["status"] == "pending"
        assert recovered_task["version"] > task["version"]

    async def test_concurrent_updates_only_one_succeeds(
        self, task_repo: TaskRepository
    ) -> None:
        """Test that concurrent updates with same version only one succeeds."""
        # Create task
        task = await task_repo.create(
            chat_id=123456,
            user_id=789,
            task_type="get_code",
            payload={"url": "https://claude.ai/auth"},
        )

        version = task["version"]

        # First update should succeed
        update1 = await task_repo.update_status(
            task_id=task["id"],
            status="done",
            expected_version=version,
            result="First",
        )

        # Second update with same version should fail
        update2 = await task_repo.update_status(
            task_id=task["id"],
            status="failed",
            expected_version=version,
            result="Second",
        )

        assert update1 is not None
        assert update2 is None

        # Verify final state matches first update
        final_task = await task_repo.get_by_id(task["id"])
        assert final_task["status"] == "done"
        assert final_task["result"] == "First"
        assert final_task["version"] == version + 1
