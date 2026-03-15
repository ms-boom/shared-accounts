"""Tests for SessionManagementService._save_debug()."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.services.session_management_service import SessionManagementService


def _make_settings(**overrides) -> MagicMock:
    from core.config import Settings

    settings = MagicMock(spec=Settings)
    settings.PLAYWRIGHT_TIMEOUT = overrides.get("timeout", 30000)
    settings.BROWSER_DEBUG = overrides.get("browser_debug", True)
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
async def test__save_debug__saves_screenshot_and_html(tmp_path: Path) -> None:
    page = _make_page()
    service = _make_service()

    await service._save_debug(page, tmp_path, "test_step")

    debug_dir = tmp_path / "debug"
    page.screenshot.assert_called_once_with(
        path=str(debug_dir / "test_step.png"), full_page=True
    )
    page.content.assert_called_once()
    assert (debug_dir / "test_step.html").exists()
    assert (debug_dir / "test_step.html").read_text() == "<html>test</html>"


@pytest.mark.unit
async def test__save_debug__browser_debug_off__skips_non_error(tmp_path: Path) -> None:
    page = _make_page()
    settings = _make_settings(browser_debug=False)
    pw = MagicMock()
    pw.chromium.launch_persistent_context = AsyncMock()
    service = SessionManagementService(settings=settings, playwright=pw)

    await service._save_debug(page, tmp_path, "01_login_page")

    page.screenshot.assert_not_called()
    page.content.assert_not_called()
    assert not (tmp_path / "debug").exists()


@pytest.mark.unit
async def test__save_debug__browser_debug_off__saves_error_steps(tmp_path: Path) -> None:
    page = _make_page()
    settings = _make_settings(browser_debug=False)
    pw = MagicMock()
    pw.chromium.launch_persistent_context = AsyncMock()
    service = SessionManagementService(settings=settings, playwright=pw)

    await service._save_debug(page, tmp_path, "error_init")

    page.screenshot.assert_called_once()
    assert (tmp_path / "debug" / "error_init.html").exists()


@pytest.mark.unit
async def test__save_debug__screenshot_fails__no_raise(tmp_path: Path) -> None:
    page = _make_page()
    page.screenshot.side_effect = RuntimeError("screenshot failed")
    service = _make_service()

    await service._save_debug(page, tmp_path, "failing_step")


@pytest.mark.unit
async def test__save_debug__creates_debug_directory(tmp_path: Path) -> None:
    page = _make_page()
    service = _make_service()
    session_path = tmp_path / "nested" / "session"

    await service._save_debug(page, session_path, "step1")

    assert (session_path / "debug").is_dir()
