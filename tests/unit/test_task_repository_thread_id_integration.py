"""Integration tests for TaskRepository thread_id with PostgreSQL.

These tests require PostgreSQL with JSONB support.
"""

import pytest

from bot.db.repositories.task_repository import TaskRepository


@pytest.fixture
def task_repo(test_database):
    """Create TaskRepository instance for testing."""
    return TaskRepository(test_database)


@pytest.mark.integration
@pytest.mark.skip(reason="Integration tests require PostgreSQL database")
async def test_tasks_isolated_by_thread_id(task_repo: TaskRepository) -> None:
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


@pytest.mark.integration
@pytest.mark.skip(reason="Integration tests require PostgreSQL database")
async def test_get_by_id_returns_thread_id(task_repo: TaskRepository) -> None:
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


@pytest.mark.integration
@pytest.mark.skip(reason="Integration tests require PostgreSQL database")
async def test_update_status_preserves_thread_id(task_repo: TaskRepository) -> None:
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


@pytest.mark.integration
@pytest.mark.skip(reason="Integration tests require PostgreSQL database")
async def test_dequeue_returns_task_with_thread_id(task_repo: TaskRepository) -> None:
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
