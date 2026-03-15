"""Tests for SessionManagementService.initialize_session()."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.exceptions import BrowserError
from core.services.session_management_service import SessionManagementService


def _make_settings() -> MagicMock:
    from core.config import Settings

    settings = MagicMock(spec=Settings)
    settings.PLAYWRIGHT_TIMEOUT = 30000
    settings.BROWSER_DEBUG = True
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
async def test__initialize_session__success__returns_email_sent(
    tmp_path: Path,
) -> None:
    page = _make_page()

    email_input = AsyncMock()
    continue_button = AsyncMock()

    def locator_side_effect(selector: str) -> AsyncMock:
        if 'type="email"' in selector:
            return email_input
        if "Continue with email" in selector:
            return continue_button
        if "Reject All Cookies" in selector:
            from patchright.async_api import TimeoutError as PlaywrightTimeoutError

            reject_mock = AsyncMock()
            reject_mock.first = reject_mock
            reject_mock.click = AsyncMock(
                side_effect=PlaywrightTimeoutError("no popup")
            )
            return reject_mock
        combined_mock = AsyncMock()
        combined_mock.or_ = MagicMock(return_value=combined_mock)
        combined_mock.first = AsyncMock()
        combined_mock.first.wait_for = AsyncMock()
        return combined_mock

    page.locator.side_effect = locator_side_effect

    text_locator = MagicMock()
    text_locator.or_ = MagicMock(return_value=text_locator)
    page.get_by_text.return_value = text_locator

    context = _make_context(page)
    playwright = _make_playwright(context)
    service = _make_service(playwright=playwright)

    session_path = tmp_path / "session"
    result = await service.initialize_session(session_path, "user@example.com")

    assert "Email sent" in result
    assert "authorization link" in result


@pytest.mark.unit
async def test__initialize_session__timeout__raises_browser_error(
    tmp_path: Path,
) -> None:
    from patchright.async_api import TimeoutError as PlaywrightTimeoutError

    page = _make_page()
    page.goto.side_effect = PlaywrightTimeoutError("page load timeout")

    context = _make_context(page)
    playwright = _make_playwright(context)
    service = _make_service(playwright=playwright)

    with pytest.raises(BrowserError, match="timed out"):
        await service.initialize_session(tmp_path / "session", "user@example.com")


@pytest.mark.unit
async def test__initialize_session__generic_error__raises_browser_error(
    tmp_path: Path,
) -> None:
    page = _make_page()
    page.goto.side_effect = RuntimeError("connection refused")

    context = _make_context(page)
    playwright = _make_playwright(context)
    service = _make_service(playwright=playwright)

    with pytest.raises(BrowserError, match="Failed to initialize session"):
        await service.initialize_session(tmp_path / "session", "user@example.com")


@pytest.mark.unit
async def test__initialize_session__always_closes_context(
    tmp_path: Path,
) -> None:
    page = _make_page()
    page.goto.side_effect = RuntimeError("fail")

    context = _make_context(page)
    playwright = _make_playwright(context)
    service = _make_service(playwright=playwright)

    with pytest.raises(BrowserError):
        await service.initialize_session(tmp_path / "session", "user@example.com")

    context.close.assert_called_once()
