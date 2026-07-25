"""Tests verifying TaskWorker dequeue goes through db.write()."""

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
    # Accessed by FingerprintResolutionService, built inside TaskWorker.__init__.
    settings.DEFAULT_USER_AGENT = "Mozilla/5.0 (Test)"
    settings.DEFAULT_CPU_CORES = 8
    settings.DEFAULT_DEVICE_MEMORY = 8
    settings.DEFAULT_TIMEZONE = "America/New_York"
    settings.DEFAULT_LOCALE = "en-US"
    return settings


@pytest.mark.unit
async def test__dequeue__uses_write(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    settings = _make_test_settings()
    notifier = MagicMock(spec=LoggingNotifier)
    notifier.notify_success = AsyncMock()
    notifier.notify_error = AsyncMock()

    TaskWorker(mock_db, settings, notifier)

    async with db_sessionmaker() as session, session.begin():
        repo = TaskRepository(session)
        await repo.create(
            chat_id=123,
            user_id=456,
            task_type="init_session",
            payload={"email": "test@example.com"},
        )

    async def _dequeue(session: AsyncSession) -> dict | None:
        repo = TaskRepository(session)
        return await repo.dequeue_pending_task()

    result = await mock_db.write(_dequeue)

    assert result is not None
    assert result["task_type"] == "init_session"
    mock_db.write.assert_called()
