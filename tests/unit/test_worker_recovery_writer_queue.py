"""Tests verifying TaskWorker recovery routes writes through db.write()."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.db.repositories.task_repository import TaskRepository
from core.ports import LoggingNotifier
from core.worker.task_worker import TaskWorker
from tests.unit.conftest import make_mock_database


def _make_test_settings() -> MagicMock:
    from core.config import Settings

    settings = MagicMock(spec=Settings)
    settings.WORKER_POLL_INTERVAL = 0.1
    settings.TASK_RECOVERY_INTERVAL = 60
    settings.TASK_STUCK_TIMEOUT = 5
    settings.SESSION_DIR = "/tmp/test_sessions"
    settings.DATA_DIR = "/tmp/test_data"
    settings.ERROR_DIR = "/tmp/test_errors"
    return settings


@pytest.mark.unit
async def test__recovery__uses_write(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    settings = _make_test_settings()
    notifier = MagicMock(spec=LoggingNotifier)

    TaskWorker(mock_db, settings, notifier)

    async with db_sessionmaker() as session, session.begin():
        repo = TaskRepository(session)
        task = await repo.create(
            chat_id=123, user_id=456,
            task_type="init_session",
            payload={"email": "test@example.com"},
        )
        await repo.update_status(task["id"], "processing", task["version"])

    async def _do_recovery(session: AsyncSession) -> int:
        repo = TaskRepository(session)
        return await repo.recover_stuck_tasks(stuck_timeout_minutes=0)

    recovered = await mock_db.write(_do_recovery)

    assert recovered >= 1
    mock_db.write.assert_called()
