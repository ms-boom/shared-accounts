"""Tests for SessionManagementService.extract_code()."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.config import Settings
from core.exceptions import BrowserError, SessionError
from core.services.session_management_service import SessionManagementService
from tests.fixtures.fake_browser import (
    FakeBrowserContext,
    FakeElement,
    FakePage,
    FakePlaywright,
    build_extract_code_scenario,
)


# ---------------------------------------------------------------------------
# Shared helpers (mock-based, for low-level edge case tests)
# ---------------------------------------------------------------------------


def _make_settings() -> MagicMock:
    settings = MagicMock(spec=Settings)
    settings.PLAYWRIGHT_TIMEOUT = 30000
    settings.BROWSER_DEBUG = True
    return settings


def _make_navigation_context() -> AsyncMock:
    """Create an async context manager mock for page.expect_navigation()."""
    nav_cm = AsyncMock()
    nav_cm.__aenter__ = AsyncMock(return_value=None)
    nav_cm.__aexit__ = AsyncMock(return_value=False)
    return nav_cm


def _make_page() -> MagicMock:
    page = AsyncMock()
    page.screenshot = AsyncMock()
    page.content = AsyncMock(return_value="<html>test</html>")
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.locator = MagicMock()
    page.get_by_text = MagicMock()
    page.expect_navigation = MagicMock(return_value=_make_navigation_context())
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


# ---------------------------------------------------------------------------
# Shared helpers (FakePage-based, for scenario tests)
# ---------------------------------------------------------------------------

AUTH_URL = "https://claude.ai/oauth/authorize?client_id=abc&scope=openid"


def _build_service(
    page: FakePage,
    *,
    browser_debug: bool = True,
) -> tuple[SessionManagementService, FakePage, FakeBrowserContext]:
    """Build service + fake browser stack from a pre-configured FakePage."""
    context = FakeBrowserContext(page)
    playwright = FakePlaywright(context)
    settings = MagicMock(spec=Settings)
    settings.PLAYWRIGHT_TIMEOUT = 30000
    settings.BROWSER_DEBUG = browser_debug
    service = SessionManagementService(settings=settings, playwright=playwright)
    return service, page, context


# ---------------------------------------------------------------------------
# Edge case tests (mock-based)
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test__extract_code__session_path_missing__raises_session_error(
    tmp_path: Path,
) -> None:
    service = _make_service()

    with pytest.raises(SessionError, match="No active session found"):
        await service.extract_code(
            tmp_path / "nonexistent", "https://claude.ai/auth/authorize?x=1"
        )


@pytest.mark.unit
async def test__extract_code__code_found_no_authorize__returns_code(
    tmp_path: Path,
) -> None:
    from patchright.async_api import TimeoutError as PlaywrightTimeoutError

    page = _make_page()

    cookie_locator = AsyncMock()
    cookie_locator.first = cookie_locator
    cookie_locator.click = AsyncMock(side_effect=PlaywrightTimeoutError("no popup"))

    authorize_locator = AsyncMock()
    authorize_locator.wait_for = AsyncMock(
        side_effect=PlaywrightTimeoutError("no button")
    )

    code_locator = AsyncMock()
    code_locator.first = code_locator
    code_locator.wait_for = AsyncMock()
    code_locator.text_content = AsyncMock(return_value="ABCD1234")

    def locator_side_effect(selector: str) -> AsyncMock:
        if "Reject All" in selector or "Accept All" in selector:
            return cookie_locator
        if "Authorize" in selector:
            return authorize_locator
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


@pytest.mark.unit
async def test__extract_code__unauthorized__raises_session_error(
    tmp_path: Path,
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


@pytest.mark.unit
async def test__extract_code__timeout__raises_browser_error(
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

    with pytest.raises(BrowserError, match="timed out"):
        await service.extract_code(
            session_path, "https://claude.ai/auth/authorize?x=1"
        )


# ---------------------------------------------------------------------------
# Scenario tests (FakePage state machine + HTML fixtures)
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test__extract_code__authorize_click_then_code_in_text__returns_code(
    tmp_path: Path,
) -> None:
    """Happy path: consent screen → click Authorize → code appears in <code> tag."""
    page = build_extract_code_scenario(
        auth_code="sk-ant-oc01-FAKE_AUTH_CODE_12345678",
    )
    service, page, context = _build_service(page)

    session_path = tmp_path / "session"
    session_path.mkdir()

    result = await service.extract_code(session_path, AUTH_URL)

    assert result == "sk-ant-oc01-FAKE_AUTH_CODE_12345678"
    assert page.state == "code_page"
    assert context.closed


@pytest.mark.unit
async def test__extract_code__authorize_click_then_code_in_input_value__returns_code(
    tmp_path: Path,
) -> None:
    """Code is in input value attribute, not text_content."""
    page = build_extract_code_scenario(
        auth_code="eyJhbGciOiJSUzI1NiJ9_token_value",
        code_in_selector='input[name="code"]',
        code_in_value=True,
    )
    service, page, context = _build_service(page)

    session_path = tmp_path / "session"
    session_path.mkdir()

    result = await service.extract_code(session_path, AUTH_URL)

    assert result == "eyJhbGciOiJSUzI1NiJ9_token_value"
    assert page.state == "code_page"


@pytest.mark.unit
async def test__extract_code__authorize_with_cookie_popup__returns_code(
    tmp_path: Path,
) -> None:
    """Cookie popup is dismissed before Authorize click."""
    page = build_extract_code_scenario(
        auth_code="CODE_WITH_COOKIES_TEST_1234",
        has_cookie_popup=True,
    )
    service, page, _ = _build_service(page)

    session_path = tmp_path / "session"
    session_path.mkdir()

    result = await service.extract_code(session_path, AUTH_URL)

    assert result == "CODE_WITH_COOKIES_TEST_1234"
    assert page.state == "code_page"


@pytest.mark.unit
async def test__extract_code__no_authorize_button__code_already_visible(
    tmp_path: Path,
) -> None:
    """No Authorize button — code is already on the page (e.g. repeat visit)."""
    page = FakePage()
    page._url_to_state = {"oauth/authorize": "code_page"}
    page._css_elements["code_page"] = {
        "code": FakeElement(text="DIRECT_CODE_NO_CONSENT_1234"),
    }
    page._html = {"code_page": "<html><code>DIRECT_CODE_NO_CONSENT_1234</code></html>"}

    service, page, _ = _build_service(page)

    session_path = tmp_path / "session"
    session_path.mkdir()

    result = await service.extract_code(session_path, AUTH_URL)

    assert result == "DIRECT_CODE_NO_CONSENT_1234"


@pytest.mark.unit
async def test__extract_code__no_authorize_no_code__raises_browser_error(
    tmp_path: Path,
) -> None:
    """Neither Authorize button nor code element — empty page."""
    page = FakePage()
    page._url_to_state = {"oauth/authorize": "empty_page"}
    page._css_elements["empty_page"] = {}
    page._html = {"empty_page": "<html><body>Something went wrong</body></html>"}

    service, page, context = _build_service(page)

    session_path = tmp_path / "session"
    session_path.mkdir()

    with pytest.raises(BrowserError):
        await service.extract_code(session_path, AUTH_URL)

    assert context.closed


@pytest.mark.unit
async def test__extract_code__debug_saves_snapshots(tmp_path: Path) -> None:
    """Debug screenshots are saved at each step."""
    page = build_extract_code_scenario(
        auth_code="DEBUG_TEST_CODE_1234567890",
    )
    service, page, _ = _build_service(page, browser_debug=True)

    session_path = tmp_path / "session"
    session_path.mkdir()

    await service.extract_code(session_path, AUTH_URL)

    debug_dir = session_path / "debug"
    assert debug_dir.exists()
    assert (debug_dir / "06_auth_page.png").exists()
    assert (debug_dir / "07_after_authorize.png").exists()


@pytest.mark.unit
async def test__extract_code__always_closes_context(tmp_path: Path) -> None:
    """Context is closed even on success."""
    page = build_extract_code_scenario(auth_code="CLOSE_TEST_CODE_123")
    service, _, context = _build_service(page)

    session_path = tmp_path / "session"
    session_path.mkdir()

    await service.extract_code(session_path, AUTH_URL)

    assert context.closed


@pytest.mark.unit
async def test__extract_code__closes_context_on_error(tmp_path: Path) -> None:
    """Context is closed when extract_code raises."""
    page = FakePage()
    page._url_to_state = {"oauth/authorize": "empty_page"}
    page._css_elements["empty_page"] = {}
    page._html = {"empty_page": "<html></html>"}

    service, _, context = _build_service(page)

    session_path = tmp_path / "session"
    session_path.mkdir()

    with pytest.raises(BrowserError):
        await service.extract_code(session_path, AUTH_URL)

    assert context.closed
