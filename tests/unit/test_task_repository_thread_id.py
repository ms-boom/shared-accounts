"""Unit tests for TaskRepository with thread_id support."""

import pytest

from bot.db.repositories.task_repository import TaskRepository
from tests.adapters import DatabasesAdapter


@pytest.mark.unit
class TestTaskRepositoryThreadId:
    """Tests for TaskRepository thread_id functionality."""

    @pytest.fixture
    def task_repo(self, test_database_adapter: DatabasesAdapter):
        """Create TaskRepository instance for testing."""
        return TaskRepository(test_database_adapter)

    async def test_create_task_with_default_thread_id(
        self, task_repo: TaskRepository
    ) -> None:
        """Test creating task with default thread_id (main chat)."""
        # SQLite doesn't support JSONB, so we skip actual task creation
        # Just verify the method signature accepts thread_id
        # For full testing, use PostgreSQL integration tests

        # This test verifies the API exists with correct parameters
        assert hasattr(task_repo, "create")
        import inspect

        sig = inspect.signature(task_repo.create)
        assert "thread_id" in sig.parameters
        assert sig.parameters["thread_id"].default == 0

    async def test_create_task_with_topic_thread_id(
        self, task_repo: TaskRepository
    ) -> None:
        """Test creating task for specific topic."""
        # This test verifies the method signature
        import inspect

        sig = inspect.signature(task_repo.create)

        # Verify thread_id parameter exists with default value
        assert "thread_id" in sig.parameters
        assert sig.parameters["thread_id"].default == 0

        # Verify all required parameters exist
        assert "chat_id" in sig.parameters
        assert "user_id" in sig.parameters
        assert "task_type" in sig.parameters
        assert "payload" in sig.parameters

    async def test_get_by_chat_id_filters_by_thread_id(
        self, task_repo: TaskRepository
    ) -> None:
        """Test get_by_chat_id can filter by thread_id."""
        # Verify method signature includes thread_id parameter
        import inspect

        sig = inspect.signature(task_repo.get_by_chat_id)

        assert "chat_id" in sig.parameters
        assert "limit" in sig.parameters
        assert "thread_id" in sig.parameters

        # thread_id should be optional (None means all threads)
        assert sig.parameters["thread_id"].default is None

    async def test_get_by_chat_id_without_thread_filter(
        self, task_repo: TaskRepository
    ) -> None:
        """Test get_by_chat_id returns tasks from all threads when thread_id=None."""
        chat_id = 123456

        # Call without thread_id filter
        tasks = await task_repo.get_by_chat_id(chat_id, limit=10)

        # Should return empty list (no tasks created)
        assert tasks == []

    async def test_get_by_chat_id_with_specific_thread(
        self, task_repo: TaskRepository
    ) -> None:
        """Test get_by_chat_id can filter by specific thread_id."""
        chat_id = 123456
        thread_id = 555

        # Call with specific thread_id
        tasks = await task_repo.get_by_chat_id(chat_id, limit=10, thread_id=thread_id)

        # Should return empty list (no tasks created)
        assert tasks == []


@pytest.mark.integration
@pytest.mark.skip(reason="Integration tests require PostgreSQL database")
class TestTaskRepositoryThreadIdIntegration:
    """Integration tests for TaskRepository thread_id with PostgreSQL.

    These tests require PostgreSQL with JSONB support.
    """

    @pytest.fixture
    def task_repo(self, test_database_adapter: DatabasesAdapter):
        """Create TaskRepository instance for testing."""
        return TaskRepository(test_database_adapter)

    async def test_tasks_isolated_by_thread_id(self, task_repo: TaskRepository) -> None:
        """Test that tasks with different thread_id are independent."""
        chat_id = 123456
        user_id = 789

        # Create task for main chat
        main_task = await task_repo.create(
            chat_id=chat_id,
            thread_id=0,
            user_id=user_id,
            task_type="init_session",
            payload={"email": "main@example.com"},
        )

        # Create task for topic 1
        topic1_task = await task_repo.create(
            chat_id=chat_id,
            thread_id=111,
            user_id=user_id,
            task_type="init_session",
            payload={"email": "topic1@example.com"},
        )

        # Create task for topic 2
        topic2_task = await task_repo.create(
            chat_id=chat_id,
            thread_id=222,
            user_id=user_id,
            task_type="get_code",
            payload={"url": "https://claude.ai/auth"},
        )

        # Verify tasks exist with correct thread_id
        assert main_task["thread_id"] == 0
        assert topic1_task["thread_id"] == 111
        assert topic2_task["thread_id"] == 222

        # Get tasks for main chat only
        main_tasks = await task_repo.get_by_chat_id(chat_id, limit=10, thread_id=0)
        assert len(main_tasks) == 1
        assert main_tasks[0]["thread_id"] == 0

        # Get tasks for topic 1 only
        topic1_tasks = await task_repo.get_by_chat_id(chat_id, limit=10, thread_id=111)
        assert len(topic1_tasks) == 1
        assert topic1_tasks[0]["thread_id"] == 111

        # Get all tasks for chat (no thread_id filter)
        all_tasks = await task_repo.get_by_chat_id(chat_id, limit=10)
        assert len(all_tasks) == 3

    async def test_get_by_id_returns_thread_id(self, task_repo: TaskRepository) -> None:
        """Test that get_by_id returns thread_id field."""
        chat_id = 123456
        thread_id = 555

        # Create task
        created = await task_repo.create(
            chat_id=chat_id,
            thread_id=thread_id,
            user_id=789,
            task_type="init_session",
            payload={"email": "test@example.com"},
        )

        # Get by ID
        task = await task_repo.get_by_id(created["id"])

        assert task is not None
        assert "thread_id" in task
        assert task["thread_id"] == thread_id
        assert task["chat_id"] == chat_id

    async def test_update_status_preserves_thread_id(
        self, task_repo: TaskRepository
    ) -> None:
        """Test that updating task status preserves thread_id."""
        chat_id = 123456
        thread_id = 666

        # Create task
        created = await task_repo.create(
            chat_id=chat_id,
            thread_id=thread_id,
            user_id=789,
            task_type="init_session",
            payload={"email": "test@example.com"},
        )

        # Update status
        updated = await task_repo.update_status(
            task_id=created["id"],
            status="processing",
        )

        assert updated is not None
        assert updated["thread_id"] == thread_id
        assert updated["status"] == "processing"

    async def test_dequeue_returns_task_with_thread_id(
        self, task_repo: TaskRepository
    ) -> None:
        """Test that dequeue_pending_task returns thread_id."""
        chat_id = 123456
        thread_id = 777

        # Create pending task
        await task_repo.create(
            chat_id=chat_id,
            thread_id=thread_id,
            user_id=789,
            task_type="get_code",
            payload={"url": "https://claude.ai/auth"},
        )

        # Dequeue task
        task = await task_repo.dequeue_pending_task()

        assert task is not None
        assert "thread_id" in task
        assert task["thread_id"] == thread_id
        assert task["chat_id"] == chat_id
        assert task["status"] == "processing"
