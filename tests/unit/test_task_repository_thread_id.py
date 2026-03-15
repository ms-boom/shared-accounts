"""Tests for TaskRepository thread_id support."""

import inspect

import pytest

from core.db.repositories.task_repository import TaskRepository


@pytest.mark.unit
async def test__create__accepts_thread_id_parameter(
    task_repository: TaskRepository,
) -> None:
    sig = inspect.signature(task_repository.create)
    assert "thread_id" in sig.parameters
    assert sig.parameters["thread_id"].default == 0


@pytest.mark.unit
async def test__create__has_all_required_parameters(
    task_repository: TaskRepository,
) -> None:
    sig = inspect.signature(task_repository.create)
    assert "chat_id" in sig.parameters
    assert "user_id" in sig.parameters
    assert "task_type" in sig.parameters
    assert "payload" in sig.parameters
    assert "thread_id" in sig.parameters


@pytest.mark.unit
async def test__get_by_chat_id__accepts_thread_id_filter(
    task_repository: TaskRepository,
) -> None:
    sig = inspect.signature(task_repository.get_by_chat_id)
    assert "chat_id" in sig.parameters
    assert "limit" in sig.parameters
    assert "thread_id" in sig.parameters
    assert sig.parameters["thread_id"].default is None


@pytest.mark.unit
async def test__get_by_chat_id__without_filter__returns_empty(
    task_repository: TaskRepository,
) -> None:
    tasks = await task_repository.get_by_chat_id(123456, limit=10)
    assert tasks == []


@pytest.mark.unit
async def test__get_by_chat_id__with_thread_filter__returns_empty(
    task_repository: TaskRepository,
) -> None:
    tasks = await task_repository.get_by_chat_id(123456, limit=10, thread_id=555)
    assert tasks == []


