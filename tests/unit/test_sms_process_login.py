"""Tests for SessionManagementService.process_login()."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.config import Settings
from core.exceptions import BrowserError, SessionError
from core.fingerprint import EffectiveFingerprint
from core.services.session_management_service import SessionManagementService


def _make_settings() -> Settings:
    """Real `Settings`, `_env_file=None` so local `.env` cannot leak into tests."""
    return Settings(
        _env_file=None,
        TELEGRAM_TOKEN="test-token",
        PLAYWRIGHT_TIMEOUT=30000,
        BROWSER_DEBUG=True,
    )


def _default_fingerprint() -> EffectiveFingerprint:
    """Fixed fingerprint value object — these tests exercise value threading,
    not fingerprint resolution (that's `FingerprintResolutionService`'s job)."""
    return EffectiveFingerprint(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
        ),
        cpu_cores=8,
        device_memory=8,
        timezone="America/New_York",
        locale="en-US",
    )


def _make_page() -> MagicMock:
    page = AsyncMock()
    page.screenshot = AsyncMock()
    page.content = AsyncMock(return_value="<html>test</html>")
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.locator = MagicMock()
    page.get_by_text = MagicMock()
    return page


def _make_context(page=None):
    context = AsyncMock()
    if page is None:
        page = _make_page()
    context.pages = [page]
    context.new_page = AsyncMock(return_value=page)
    context.close = AsyncMock()
    return context


def _make_playwright(context=None):
    pw = MagicMock()
    if context is None:
        context = _make_context()
    pw.chromium.launch_persistent_context = AsyncMock(return_value=context)
    return pw


def _make_service(playwright=None):
    settings = _make_settings()
    if playwright is None:
        playwright = _make_playwright()
    return SessionManagementService(settings=settings, playwright=playwright)


@pytest.mark.unit
async def test__process_login__session_path_missing__raises_session_error(
    tmp_path: Path,
) -> None:
    service = _make_service()

    with pytest.raises(SessionError, match="No session found"):
        await service.process_login(
            tmp_path / "nonexistent",
            "https://claude.ai/login?token=x",
            fingerprint=_default_fingerprint(),
        )


@pytest.mark.unit
async def test__process_login__success__returns_success_message(
    tmp_path: Path,
) -> None:
    from patchright.async_api import TimeoutError as PlaywrightTimeoutError

    page = _make_page()

    # Chat input locator — indicates successful auth
    chat_input = MagicMock()
    chat_input.first = AsyncMock()
    chat_input.first.wait_for = AsyncMock()

    def locator_side_effect(selector: str) -> MagicMock:
        if "Reject All Cookies" in selector:
            cookie_mock = AsyncMock()
            cookie_mock.first = cookie_mock
            cookie_mock.click = AsyncMock(
                side_effect=PlaywrightTimeoutError("no popup")
            )
            return cookie_mock
        if "chat-input" in selector:
            return chat_input
        return MagicMock()

    page.locator.side_effect = locator_side_effect

    context = _make_context(page)
    playwright = _make_playwright(context)
    service = _make_service(playwright=playwright)

    session_path = tmp_path / "session"
    session_path.mkdir()

    result = await service.process_login(
        session_path,
        "https://claude.ai/login?token=valid",
        fingerprint=_default_fingerprint(),
    )

    assert "Session initialized successfully" in result
    context.close.assert_called_once()


@pytest.mark.unit
async def test__process_login__timeout__raises_browser_error(
    tmp_path: Path,
) -> None:
    from patchright.async_api import TimeoutError as PlaywrightTimeoutError

    page = _make_page()
    page.goto.side_effect = PlaywrightTimeoutError("timeout")

    context = _make_context(page)
    playwright = _make_playwright(context)
    service = _make_service(playwright=playwright)

    session_path = tmp_path / "session"
    session_path.mkdir()

    with pytest.raises(BrowserError, match="invalid or expired"):
        await service.process_login(
            session_path,
            "https://claude.ai/login?token=expired",
            fingerprint=_default_fingerprint(),
        )
