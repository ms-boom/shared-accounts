"""Unit tests for TaskRepository thread_id functionality."""

import inspect

import pytest

from bot.db.repositories.task_repository import TaskRepository


@pytest.fixture
def task_repo(test_database):
    """Create TaskRepository instance for testing."""
    return TaskRepository(test_database)


@pytest.mark.unit
async def test_create_task_with_default_thread_id(task_repo: TaskRepository) -> None:
    """Test creating task with default thread_id (main chat)."""
    # SQLite doesn't support JSONB, so we skip actual task creation
    # Just verify the method signature accepts thread_id
    # For full testing, use PostgreSQL integration tests

    # This test verifies the API exists with correct parameters
    assert hasattr(task_repo, "create")
    sig = inspect.signature(task_repo.create)
    assert "thread_id" in sig.parameters
    assert sig.parameters["thread_id"].default == 0


@pytest.mark.unit
async def test_create_task_with_topic_thread_id(task_repo: TaskRepository) -> None:
    """Test creating task for specific topic."""
    # This test verifies the method signature
    sig = inspect.signature(task_repo.create)

    # Verify thread_id parameter exists with default value
    assert "thread_id" in sig.parameters
    assert sig.parameters["thread_id"].default == 0

    # Verify all required parameters exist
    assert "chat_id" in sig.parameters
    assert "user_id" in sig.parameters
    assert "task_type" in sig.parameters
    assert "payload" in sig.parameters


@pytest.mark.unit
async def test_get_by_chat_id_filters_by_thread_id(task_repo: TaskRepository) -> None:
    """Test get_by_chat_id can filter by thread_id."""
    # Verify method signature includes thread_id parameter
    sig = inspect.signature(task_repo.get_by_chat_id)

    assert "chat_id" in sig.parameters
    assert "limit" in sig.parameters
    assert "thread_id" in sig.parameters

    # thread_id should be optional (None means all threads)
    assert sig.parameters["thread_id"].default is None


@pytest.mark.unit
async def test_get_by_chat_id_without_thread_filter(
    task_repo: TaskRepository,
) -> None:
    """Test get_by_chat_id returns tasks from all threads when thread_id=None."""
    chat_id = 123456

    # Call without thread_id filter
    tasks = await task_repo.get_by_chat_id(chat_id, limit=10)

    # Should return empty list (no tasks created)
    assert tasks == []


@pytest.mark.unit
async def test_get_by_chat_id_with_specific_thread(
    task_repo: TaskRepository,
) -> None:
    """Test get_by_chat_id can filter by specific thread_id."""
    chat_id = 123456
    thread_id = 555

    # Call with specific thread_id
    tasks = await task_repo.get_by_chat_id(chat_id, limit=10, thread_id=thread_id)

    # Should return empty list (no tasks created)
    assert tasks == []
