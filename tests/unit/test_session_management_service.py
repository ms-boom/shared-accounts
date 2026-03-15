"""Unit tests for SessionManagementService.

Tests cover _save_debug, _dismiss_cookie_popup, initialize_session,
process_login, and extract_code with mocked Playwright objects.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.exceptions import BrowserError, SessionError
from core.services.session_management_service import SessionManagementService


def _make_settings(**overrides) -> MagicMock:  # noqa: ANN003
    """Create minimal Settings mock for SessionManagementService."""
    from core.config import Settings

    settings = MagicMock(spec=Settings)
    settings.PLAYWRIGHT_TIMEOUT = overrides.get("timeout", 30000)
    return settings


def _make_page() -> MagicMock:
    """Create a mock Playwright Page."""
    page = AsyncMock()
    page.screenshot = AsyncMock()
    page.content = AsyncMock(return_value="<html>test</html>")
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.locator = MagicMock()
    page.get_by_text = MagicMock()
    return page


def _make_context(page: AsyncMock | None = None) -> AsyncMock:
    """Create a mock BrowserContext with a page."""
    context = AsyncMock()
    if page is None:
        page = _make_page()
    context.pages = [page]
    context.new_page = AsyncMock(return_value=page)
    context.close = AsyncMock()
    return context


def _make_playwright(context: AsyncMock | None = None) -> MagicMock:
    """Create a mock Playwright instance."""
    pw = MagicMock()
    if context is None:
        context = _make_context()
    pw.chromium.launch_persistent_context = AsyncMock(return_value=context)
    return pw


def _make_service(
    playwright: MagicMock | None = None,
    **settings_overrides,  # noqa: ANN003
) -> SessionManagementService:
    """Create SessionManagementService with mocked dependencies."""
    settings = _make_settings(**settings_overrides)
    if playwright is None:
        playwright = _make_playwright()
    return SessionManagementService(settings=settings, playwright=playwright)


@pytest.mark.unit
class TestSaveDebug:
    """Tests for SessionManagementService._save_debug()."""

    async def test__save_debug__normal_page__saves_screenshot_and_html(
        self, tmp_path: Path
    ) -> None:
        page = _make_page()
        service = _make_service()

        await service._save_debug(page, tmp_path, "test_step")

        debug_dir = tmp_path / "debug"
        page.screenshot.assert_called_once_with(
            path=str(debug_dir / "test_step.png"),
            full_page=True,
        )
        page.content.assert_called_once()
        assert (debug_dir / "test_step.html").exists()
        assert (debug_dir / "test_step.html").read_text() == "<html>test</html>"

    async def test__save_debug__screenshot_fails__logs_warning_no_raise(
        self, tmp_path: Path
    ) -> None:
        page = _make_page()
        page.screenshot.side_effect = RuntimeError("screenshot failed")
        service = _make_service()

        # Should not raise
        await service._save_debug(page, tmp_path, "failing_step")

    async def test__save_debug__creates_debug_directory(
        self, tmp_path: Path
    ) -> None:
        page = _make_page()
        service = _make_service()
        session_path = tmp_path / "nested" / "session"

        await service._save_debug(page, session_path, "step1")

        assert (session_path / "debug").is_dir()


@pytest.mark.unit
class TestDismissCookiePopup:
    """Tests for SessionManagementService._dismiss_cookie_popup()."""

    async def test__dismiss_cookie_popup__button_present__clicks_it(self) -> None:
        page = _make_page()
        locator_mock = AsyncMock()
        locator_mock.first = locator_mock
        locator_mock.click = AsyncMock()
        page.locator.return_value = locator_mock
        service = _make_service()

        await service._dismiss_cookie_popup(page)

        page.locator.assert_called_once()
        locator_mock.click.assert_called_once_with(timeout=3000)

    async def test__dismiss_cookie_popup__no_button__silently_passes(self) -> None:
        from patchright.async_api import TimeoutError as PlaywrightTimeoutError

        page = _make_page()
        locator_mock = AsyncMock()
        locator_mock.first = locator_mock
        locator_mock.click = AsyncMock(
            side_effect=PlaywrightTimeoutError("timeout")
        )
        page.locator.return_value = locator_mock
        service = _make_service()

        # Should not raise
        await service._dismiss_cookie_popup(page)


@pytest.mark.unit
class TestInitializeSession:
    """Tests for SessionManagementService.initialize_session()."""

    async def test__initialize_session__success__returns_email_sent_message(
        self, tmp_path: Path
    ) -> None:
        page = _make_page()

        # Setup locators for email input and continue button
        email_input = AsyncMock()
        continue_button = AsyncMock()

        # locator() returns different things based on selector
        def locator_side_effect(selector: str) -> AsyncMock:
            if 'type="email"' in selector:
                return email_input
            if "Continue with email" in selector:
                return continue_button
            if "Reject All Cookies" in selector:
                reject_mock = AsyncMock()
                reject_mock.first = reject_mock
                from patchright.async_api import (
                    TimeoutError as PlaywrightTimeoutError,
                )
                reject_mock.click = AsyncMock(
                    side_effect=PlaywrightTimeoutError("no popup")
                )
                return reject_mock
            # For code input locator
            combined_mock = AsyncMock()
            combined_mock.or_ = MagicMock(return_value=combined_mock)
            combined_mock.first = AsyncMock()
            combined_mock.first.wait_for = AsyncMock()
            return combined_mock

        page.locator.side_effect = locator_side_effect

        # get_by_text returns a mock that supports .or_()
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

    async def test__initialize_session__timeout__raises_browser_error(
        self, tmp_path: Path
    ) -> None:
        from patchright.async_api import TimeoutError as PlaywrightTimeoutError

        page = _make_page()
        page.goto.side_effect = PlaywrightTimeoutError("page load timeout")

        context = _make_context(page)
        playwright = _make_playwright(context)
        service = _make_service(playwright=playwright)

        session_path = tmp_path / "session"
        with pytest.raises(BrowserError, match="timed out"):
            await service.initialize_session(session_path, "user@example.com")

    async def test__initialize_session__generic_error__raises_browser_error(
        self, tmp_path: Path
    ) -> None:
        page = _make_page()
        page.goto.side_effect = RuntimeError("connection refused")

        context = _make_context(page)
        playwright = _make_playwright(context)
        service = _make_service(playwright=playwright)

        session_path = tmp_path / "session"
        with pytest.raises(BrowserError, match="Failed to initialize session"):
            await service.initialize_session(session_path, "user@example.com")

    async def test__initialize_session__always_closes_context(
        self, tmp_path: Path
    ) -> None:
        page = _make_page()
        page.goto.side_effect = RuntimeError("fail")

        context = _make_context(page)
        playwright = _make_playwright(context)
        service = _make_service(playwright=playwright)

        session_path = tmp_path / "session"
        with pytest.raises(BrowserError):
            await service.initialize_session(session_path, "user@example.com")

        context.close.assert_called_once()


@pytest.mark.unit
class TestProcessLogin:
    """Tests for SessionManagementService.process_login()."""

    async def test__process_login__session_path_missing__raises_session_error(
        self, tmp_path: Path
    ) -> None:
        service = _make_service()
        missing_path = tmp_path / "nonexistent"

        with pytest.raises(SessionError, match="No session found"):
            await service.process_login(missing_path, "https://claude.ai/login?token=x")

    async def test__process_login__success__returns_success_message(
        self, tmp_path: Path
    ) -> None:
        page = _make_page()

        # Cookie popup no-op
        cookie_locator = AsyncMock()
        cookie_locator.first = cookie_locator
        from patchright.async_api import TimeoutError as PlaywrightTimeoutError
        cookie_locator.click = AsyncMock(
            side_effect=PlaywrightTimeoutError("no popup")
        )
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

    async def test__process_login__timeout__raises_browser_error(
        self, tmp_path: Path
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


@pytest.mark.unit
class TestExtractCode:
    """Tests for SessionManagementService.extract_code()."""

    async def test__extract_code__session_path_missing__raises_session_error(
        self, tmp_path: Path
    ) -> None:
        service = _make_service()
        missing_path = tmp_path / "nonexistent"

        with pytest.raises(SessionError, match="No active session found"):
            await service.extract_code(
                missing_path, "https://claude.ai/auth/authorize?x=1"
            )

    async def test__extract_code__code_found_in_element__returns_code(
        self, tmp_path: Path
    ) -> None:
        page = _make_page()

        # Cookie popup no-op
        from patchright.async_api import TimeoutError as PlaywrightTimeoutError
        cookie_locator = AsyncMock()
        cookie_locator.first = cookie_locator
        cookie_locator.click = AsyncMock(
            side_effect=PlaywrightTimeoutError("no popup")
        )

        # Code element locator
        code_locator = AsyncMock()
        code_locator.first = code_locator
        code_locator.wait_for = AsyncMock()
        code_locator.text_content = AsyncMock(return_value="ABCD1234")

        call_count = 0

        def locator_side_effect(selector: str) -> AsyncMock:
            nonlocal call_count
            if "Reject All" in selector or "Accept All" in selector:
                return cookie_locator
            call_count += 1
            if call_count == 1:
                return code_locator
            return code_locator

        page.locator.side_effect = locator_side_effect

        context = _make_context(page)
        playwright = _make_playwright(context)
        service = _make_service(playwright=playwright)

        session_path = tmp_path / "session"
        session_path.mkdir()

        result = await service.extract_code(
            session_path, "https://claude.ai/auth/authorize?x=1"
        )

        assert result == "ABCD1234"
        context.close.assert_called_once()

    async def test__extract_code__unauthorized_error__raises_session_error(
        self, tmp_path: Path
    ) -> None:
        page = _make_page()
        page.goto.side_effect = RuntimeError("401 Unauthorized")

        context = _make_context(page)
        playwright = _make_playwright(context)
        service = _make_service(playwright=playwright)

        session_path = tmp_path / "session"
        session_path.mkdir()

        with pytest.raises(SessionError, match="Session expired or invalid"):
            await service.extract_code(
                session_path, "https://claude.ai/auth/authorize?x=1"
            )

    async def test__extract_code__timeout__raises_browser_error(
        self, tmp_path: Path
    ) -> None:
        from patchright.async_api import TimeoutError as PlaywrightTimeoutError

        page = _make_page()
        page.goto.side_effect = PlaywrightTimeoutError("timeout")

        context = _make_context(page)
        playwright = _make_playwright(context)
        service = _make_service(playwright=playwright)

        session_path = tmp_path / "session"
        session_path.mkdir()

        with pytest.raises(BrowserError, match="timed out"):
            await service.extract_code(
                session_path, "https://claude.ai/auth/authorize?x=1"
            )
