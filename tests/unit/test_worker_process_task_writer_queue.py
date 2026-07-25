"""Tests verifying TaskWorker process_task routes writes through db.write()."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.db.repositories.chat_session_repository import ChatSessionRepository
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
async def test__process_init_session__uses_write(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    settings = _make_test_settings()
    notifier = MagicMock(spec=LoggingNotifier)
    notifier.notify_success = AsyncMock()

    worker = TaskWorker(mock_db, settings, notifier)
    worker.playwright = MagicMock()
    worker.playwright.initialize_session = AsyncMock(
        return_value=("/data/sessions/123", "Session initialized")
    )

    async with db_sessionmaker() as session, session.begin():
        repo = TaskRepository(session)
        task = await repo.create(
            chat_id=123,
            user_id=456,
            task_type="init_session",
            payload={"email": "test@example.com"},
        )

    await worker.process_init_session(
        task_id=str(task["id"]),
        chat_id=123,
        thread_id=0,
        payload={"email": "test@example.com"},
        version=task["version"],
    )

    mock_db.write.assert_called_once()


@pytest.mark.unit
async def test__process_login_link__uses_write(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    settings = _make_test_settings()
    notifier = MagicMock(spec=LoggingNotifier)
    notifier.notify_success = AsyncMock()

    worker = TaskWorker(mock_db, settings, notifier)
    worker.playwright = MagicMock()
    worker.playwright.process_login_link = AsyncMock(return_value="Login processed")

    async with db_sessionmaker() as session, session.begin():
        repo = TaskRepository(session)
        task = await repo.create(
            chat_id=123,
            user_id=456,
            task_type="process_login_link",
            payload={"login_url": "https://example.com/login"},
        )

    await worker.process_login_link(
        task_id=str(task["id"]),
        chat_id=123,
        thread_id=0,
        payload={"login_url": "https://example.com/login"},
        version=task["version"],
    )

    mock_db.write.assert_called_once()


@pytest.mark.unit
async def test__process_get_code__uses_write(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    settings = _make_test_settings()
    notifier = MagicMock(spec=LoggingNotifier)
    notifier.notify_success = AsyncMock()

    worker = TaskWorker(mock_db, settings, notifier)
    worker.playwright = MagicMock()
    worker.playwright.extract_authorization_code = AsyncMock(
        return_value="AUTH-CODE-123"
    )

    async with db_sessionmaker() as session, session.begin():
        session_repo = ChatSessionRepository(session)
        await session_repo.create(
            chat_id=123,
            email="test@example.com",
            session_path="/data/sessions/123",
        )
        task_repo = TaskRepository(session)
        task = await task_repo.create(
            chat_id=123,
            user_id=456,
            task_type="get_code",
            payload={"auth_url": "https://claude.ai/auth/authorize?test=1"},
        )

    await worker.process_get_code(
        task_id=str(task["id"]),
        chat_id=123,
        thread_id=0,
        payload={"auth_url": "https://claude.ai/auth/authorize?test=1"},
        version=task["version"],
    )

    mock_db.write.assert_called_once()


@pytest.mark.unit
async def test__process_task__error__uses_write(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    mock_db = make_mock_database(db_sessionmaker)
    settings = _make_test_settings()
    notifier = MagicMock(spec=LoggingNotifier)
    notifier.notify_error = AsyncMock()

    worker = TaskWorker(mock_db, settings, notifier)
    worker.playwright = MagicMock()
    worker.playwright.initialize_session = AsyncMock(
        side_effect=Exception("Browser crashed")
    )

    async with db_sessionmaker() as session, session.begin():
        repo = TaskRepository(session)
        task = await repo.create(
            chat_id=123,
            user_id=456,
            task_type="init_session",
            payload={"email": "test@example.com"},
        )

    await worker.process_task(task)

    mock_db.write.assert_called()
