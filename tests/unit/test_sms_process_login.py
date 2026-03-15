"""Tests for SessionManagementService.process_login()."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.exceptions import BrowserError, SessionError
from core.services.session_management_service import SessionManagementService


def _make_settings() -> MagicMock:
    from core.config import Settings

    settings = MagicMock(spec=Settings)
    settings.PLAYWRIGHT_TIMEOUT = 30000
    return settings


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
            tmp_path / "nonexistent", "https://claude.ai/login?token=x"
        )


@pytest.mark.unit
async def test__process_login__success__returns_success_message(
    tmp_path: Path,
) -> None:
    from patchright.async_api import TimeoutError as PlaywrightTimeoutError

    page = _make_page()
    cookie_locator = AsyncMock()
    cookie_locator.first = cookie_locator
    cookie_locator.click = AsyncMock(side_effect=PlaywrightTimeoutError("no popup"))
    page.locator.return_value = cookie_locator

    context = _make_context(page)
    playwright = _make_playwright(context)
    service = _make_service(playwright=playwright)

    session_path = tmp_path / "session"
    session_path.mkdir()

    result = await service.process_login(
        session_path, "https://claude.ai/login?token=valid"
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
            session_path, "https://claude.ai/login?token=expired"
        )
