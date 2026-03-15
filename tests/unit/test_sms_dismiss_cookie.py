"""Tests for SessionManagementService._dismiss_cookie_popup()."""

from unittest.mock import AsyncMock, MagicMock

import pytest

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


def _make_service() -> SessionManagementService:
    settings = _make_settings()
    pw = MagicMock()
    pw.chromium.launch_persistent_context = AsyncMock()
    return SessionManagementService(settings=settings, playwright=pw)


@pytest.mark.unit
async def test__dismiss_cookie_popup__button_present__clicks_it() -> None:
    page = _make_page()
    locator_mock = AsyncMock()
    locator_mock.first = locator_mock
    locator_mock.click = AsyncMock()
    page.locator.return_value = locator_mock
    service = _make_service()

    await service._dismiss_cookie_popup(page)

    page.locator.assert_called_once()
    locator_mock.click.assert_called_once_with(timeout=3000)


@pytest.mark.unit
async def test__dismiss_cookie_popup__no_button__silently_passes() -> None:
    from patchright.async_api import TimeoutError as PlaywrightTimeoutError

    page = _make_page()
    locator_mock = AsyncMock()
    locator_mock.first = locator_mock
    locator_mock.click = AsyncMock(side_effect=PlaywrightTimeoutError("timeout"))
    page.locator.return_value = locator_mock
    service = _make_service()

    await service._dismiss_cookie_popup(page)
