"""Tests for `PlaywrightService`'s fingerprint-resolution wiring.

Covers the (b) contract from the architecture: `PlaywrightService` owns the
resolve call — each public method resolves per operation (no caching) and
threads the resulting `EffectiveFingerprint` down to `SessionManagementService`.
`_resolve` itself falls back to the default profile when no `Database` is
attached (CLI/path-only usage has no chat_id/thread_id binding to look up).
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.config import Settings
from core.fingerprint import EffectiveFingerprint
from core.worker.playwright_service import PlaywrightService


def _make_settings(session_dir: Path) -> Settings:
    """Real `Settings`, `_env_file=None` so local `.env` cannot leak into tests."""
    return Settings(
        _env_file=None,
        TELEGRAM_TOKEN="test-token",
        SESSION_DIR=session_dir,
    )


def _custom_fingerprint() -> EffectiveFingerprint:
    return EffectiveFingerprint(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) CustomTestAgent/1.0",
        cpu_cores=6,
        device_memory=4,
        timezone="Europe/Berlin",
        locale="de-DE",
    )


class _FakeReadSession:
    """Async context manager standing in for `Database.read()`'s AsyncSession."""

    def __init__(self, session: object) -> None:
        self._session = session

    async def __aenter__(self) -> object:
        return self._session

    async def __aexit__(self, *args: object) -> bool:
        return False


class _FakeDatabase:
    """Minimal `Database` stand-in exposing only `.read()`."""

    def __init__(self, session: object) -> None:
        self._session = session

    def read(self) -> _FakeReadSession:
        return _FakeReadSession(self._session)


@pytest.mark.unit
async def test__resolve__no_database__returns_resolution_service_default(
    tmp_path: Path,
) -> None:
    resolution_service = MagicMock()
    resolution_service.default = MagicMock(return_value=_custom_fingerprint())
    service = PlaywrightService(
        _make_settings(tmp_path), resolution_service, database=None
    )

    result = await service._resolve(chat_id=123, thread_id=0)

    assert result == _custom_fingerprint()
    resolution_service.default.assert_called_once()


@pytest.mark.unit
async def test__resolve__with_database__resolves_via_read_session(
    tmp_path: Path,
) -> None:
    resolution_service = MagicMock()
    resolution_service.resolve = AsyncMock(return_value=_custom_fingerprint())
    fake_session = object()
    database = _FakeDatabase(fake_session)
    service = PlaywrightService(
        _make_settings(tmp_path), resolution_service, database=database
    )

    result = await service._resolve(chat_id=123, thread_id=5)

    assert result == _custom_fingerprint()
    resolution_service.resolve.assert_called_once_with(fake_session, 123, 5)


@pytest.mark.unit
async def test__resolve__called_per_operation_not_cached(tmp_path: Path) -> None:
    """A fingerprint edited between two operations takes effect on the next one."""
    first_fp = _custom_fingerprint()
    second_fp = EffectiveFingerprint(
        user_agent="UA-2",
        cpu_cores=2,
        device_memory=2,
        timezone="UTC",
        locale="en",
    )
    resolution_service = MagicMock()
    resolution_service.resolve = AsyncMock(side_effect=[first_fp, second_fp])
    database = _FakeDatabase(object())
    service = PlaywrightService(
        _make_settings(tmp_path), resolution_service, database=database
    )

    result_1 = await service._resolve(chat_id=123, thread_id=0)
    result_2 = await service._resolve(chat_id=123, thread_id=0)

    assert result_1 == first_fp
    assert result_2 == second_fp
    assert resolution_service.resolve.call_count == 2


@pytest.mark.unit
async def test__initialize_session__passes_resolved_fingerprint_down(
    tmp_path: Path,
) -> None:
    resolution_service = MagicMock()
    resolution_service.default = MagicMock(return_value=_custom_fingerprint())
    service = PlaywrightService(
        _make_settings(tmp_path), resolution_service, database=None
    )
    service._session_service = AsyncMock()
    service._session_service.initialize_session = AsyncMock(return_value="ok")

    await service.initialize_session(chat_id=123, email="a@b.com", thread_id=0)

    _, kwargs = service._session_service.initialize_session.call_args
    assert kwargs["fingerprint"] == _custom_fingerprint()


@pytest.mark.unit
async def test__process_login_link__passes_resolved_fingerprint_down(
    tmp_path: Path,
) -> None:
    resolution_service = MagicMock()
    resolution_service.default = MagicMock(return_value=_custom_fingerprint())
    service = PlaywrightService(
        _make_settings(tmp_path), resolution_service, database=None
    )
    service._session_service = AsyncMock()
    service._session_service.process_login = AsyncMock(return_value="ok")

    await service.process_login_link(
        chat_id=123, login_url="https://claude.ai/login?token=x", thread_id=0
    )

    _, kwargs = service._session_service.process_login.call_args
    assert kwargs["fingerprint"] == _custom_fingerprint()


@pytest.mark.unit
async def test__extract_authorization_code__passes_resolved_fingerprint_down(
    tmp_path: Path,
) -> None:
    resolution_service = MagicMock()
    resolution_service.default = MagicMock(return_value=_custom_fingerprint())
    service = PlaywrightService(
        _make_settings(tmp_path), resolution_service, database=None
    )
    service._session_service = AsyncMock()
    service._session_service.extract_code = AsyncMock(return_value="CODE123")

    await service.extract_authorization_code(
        chat_id=123, auth_url="https://claude.ai/oauth/authorize?x=1", thread_id=0
    )

    _, kwargs = service._session_service.extract_code.call_args
    assert kwargs["fingerprint"] == _custom_fingerprint()
