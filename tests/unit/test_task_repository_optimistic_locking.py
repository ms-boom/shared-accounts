"""Tests for TaskRepository optimistic locking functionality."""

import inspect

import pytest

from core.db.repositories.task_repository import TaskRepository


@pytest.mark.unit
async def test__update_status__requires_version_parameter(
    task_repository: TaskRepository,
) -> None:
    sig = inspect.signature(task_repository.update_status)

    assert "expected_version" in sig.parameters
    assert "task_id" in sig.parameters
    assert "status" in sig.parameters
    assert "result" in sig.parameters
    assert sig.parameters["expected_version"].default == inspect.Parameter.empty


@pytest.mark.unit
async def test__recover_stuck_tasks__method_exists(
    task_repository: TaskRepository,
) -> None:
    assert hasattr(task_repository, "recover_stuck_tasks")

    sig = inspect.signature(task_repository.recover_stuck_tasks)
    assert "stuck_timeout_minutes" in sig.parameters
    assert sig.parameters["stuck_timeout_minutes"].default == 5
