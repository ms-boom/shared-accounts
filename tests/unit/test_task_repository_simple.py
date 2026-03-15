"""Simplified unit tests for TaskRepository (SQLite compatible)."""

import pytest

from core.db.repositories.task_repository import TaskRepository


@pytest.mark.unit
async def test__gets_pending_count__initially_zero(
    task_repository: TaskRepository,
) -> None:
    count = await task_repository.get_pending_count()
    assert count == 0


