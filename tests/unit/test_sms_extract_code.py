"""Tests for SessionManagementService.extract_code().

Covers the code extraction flow on the Claude "Authentication Code" page:
- Code is extracted from <pre> tag after "Authentication Code" heading appears
- Authorize button click flow before code extraction
- Error cases: empty code, short code, missing elements
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.config import Settings
from core.exceptions import BrowserError, SessionError
from core.fingerprint import EffectiveFingerprint
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
    settings = Settings(
        _env_file=None,
        TELEGRAM_TOKEN="test-token",
        PLAYWRIGHT_TIMEOUT=30000,
        BROWSER_DEBUG=browser_debug,
    )
    service = SessionManagementService(settings=settings, playwright=playwright)
    return service, page, context


def _build_code_page(
    *,
    auth_code: str = "",
    has_heading: bool = True,
    has_pre: bool = True,
) -> FakePage:
    """Build a FakePage that lands directly on the code page (no consent screen).

    Useful for testing code extraction in isolation without Authorize button flow.
    """
    page = FakePage()
    page._url_to_state = {"oauth/authorize": "code_page"}

    text_elements: dict[str, FakeElement] = {}
    if has_heading:
        text_elements["Authentication Code"] = FakeElement(
            text="Authentication Code",
        )
    page._text_elements["code_page"] = text_elements

    css_elements: dict[str, FakeElement] = {}
    if has_pre:
        css_elements["pre"] = FakeElement(text=auth_code)
    page._css_elements["code_page"] = css_elements

    page._html = {
        "code_page": "<html><h3>Authentication Code</h3><pre>"
        + auth_code
        + "</pre></html>"
    }

    return page


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
            tmp_path / "nonexistent",
            "https://claude.ai/auth/authorize?x=1",
            fingerprint=_default_fingerprint(),
        )


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
            session_path,
            "https://claude.ai/auth/authorize?x=1",
            fingerprint=_default_fingerprint(),
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
            session_path,
            "https://claude.ai/auth/authorize?x=1",
            fingerprint=_default_fingerprint(),
        )


# ---------------------------------------------------------------------------
# Code extraction from <pre> tag (FakePage scenario tests)
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test__extract_code__reads_code_from_pre_tag(tmp_path: Path) -> None:
    """Code is extracted from <pre> tag text content after heading appears."""
    valid_code = "t0W3NtDRX8TKw2dLubFXgmNANZH4cT5cpqvG1L9pLYgRwjjE"
    page = _build_code_page(auth_code=valid_code)
    service, _, context = _build_service(page)

    session_path = tmp_path / "session"
    session_path.mkdir()

    result = await service.extract_code(
        session_path, AUTH_URL, fingerprint=_default_fingerprint()
    )

    assert result == valid_code
    assert context.closed


@pytest.mark.unit
async def test__extract_code__strips_whitespace_from_pre_content(
    tmp_path: Path,
) -> None:
    """Whitespace around code in <pre> is stripped."""
    page = _build_code_page(auth_code="  CODE_WITH_WHITESPACE_1234567  ")
    service, _, _ = _build_service(page)

    session_path = tmp_path / "session"
    session_path.mkdir()

    result = await service.extract_code(
        session_path, AUTH_URL, fingerprint=_default_fingerprint()
    )

    assert result == "CODE_WITH_WHITESPACE_1234567"


@pytest.mark.unit
async def test__extract_code__pre_empty__raises_browser_error(
    tmp_path: Path,
) -> None:
    """Empty <pre> tag triggers BrowserError with 'empty' message."""
    page = _build_code_page(auth_code="")
    service, _, context = _build_service(page)

    session_path = tmp_path / "session"
    session_path.mkdir()

    with pytest.raises(BrowserError, match="empty"):
        await service.extract_code(
            session_path, AUTH_URL, fingerprint=_default_fingerprint()
        )

    assert context.closed


@pytest.mark.unit
async def test__extract_code__code_too_short__raises_browser_error(
    tmp_path: Path,
) -> None:
    """Code shorter than 20 characters is treated as invalid."""
    page = _build_code_page(auth_code="short")
    service, _, context = _build_service(page)

    session_path = tmp_path / "session"
    session_path.mkdir()

    with pytest.raises(BrowserError, match="empty"):
        await service.extract_code(
            session_path, AUTH_URL, fingerprint=_default_fingerprint()
        )

    assert context.closed


@pytest.mark.unit
async def test__extract_code__no_heading__raises_browser_error(
    tmp_path: Path,
) -> None:
    """Missing 'Authentication Code' heading causes timeout -> BrowserError."""
    page = _build_code_page(
        auth_code="VALID_CODE_THAT_WONT_BE_REACHED_1234",
        has_heading=False,
    )
    service, _, context = _build_service(page)

    session_path = tmp_path / "session"
    session_path.mkdir()

    with pytest.raises(BrowserError, match="timed out"):
        await service.extract_code(
            session_path, AUTH_URL, fingerprint=_default_fingerprint()
        )

    assert context.closed


@pytest.mark.unit
async def test__extract_code__no_pre_element__raises_browser_error(
    tmp_path: Path,
) -> None:
    """Heading present but no <pre> element causes timeout -> BrowserError."""
    page = _build_code_page(
        auth_code="",
        has_pre=False,
    )
    service, _, context = _build_service(page)

    session_path = tmp_path / "session"
    session_path.mkdir()

    with pytest.raises(BrowserError, match="timed out"):
        await service.extract_code(
            session_path, AUTH_URL, fingerprint=_default_fingerprint()
        )

    assert context.closed


# ---------------------------------------------------------------------------
# Authorize button flow (FakePage scenario tests)
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test__extract_code__authorize_click_then_code_in_pre__returns_code(
    tmp_path: Path,
) -> None:
    """Happy path: consent screen -> click Authorize -> code appears in <pre>."""
    page = build_extract_code_scenario(
        auth_code="sk-ant-oc01-FAKE_AUTH_CODE_12345678",
    )
    service, page, context = _build_service(page)

    session_path = tmp_path / "session"
    session_path.mkdir()

    result = await service.extract_code(
        session_path, AUTH_URL, fingerprint=_default_fingerprint()
    )

    assert result == "sk-ant-oc01-FAKE_AUTH_CODE_12345678"
    assert page.state == "code_page"
    assert context.closed


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

    result = await service.extract_code(
        session_path, AUTH_URL, fingerprint=_default_fingerprint()
    )

    assert result == "CODE_WITH_COOKIES_TEST_1234"
    assert page.state == "code_page"


@pytest.mark.unit
async def test__extract_code__no_authorize_button__code_already_visible(
    tmp_path: Path,
) -> None:
    """No Authorize button -- code page is shown directly (e.g. repeat visit)."""
    page = _build_code_page(auth_code="DIRECT_CODE_NO_CONSENT_1234")
    service, page, _ = _build_service(page)

    session_path = tmp_path / "session"
    session_path.mkdir()

    result = await service.extract_code(
        session_path, AUTH_URL, fingerprint=_default_fingerprint()
    )

    assert result == "DIRECT_CODE_NO_CONSENT_1234"


@pytest.mark.unit
async def test__extract_code__no_authorize_no_code__raises_browser_error(
    tmp_path: Path,
) -> None:
    """Neither Authorize button nor code element -- empty page."""
    page = FakePage()
    page._url_to_state = {"oauth/authorize": "empty_page"}
    page._css_elements["empty_page"] = {}
    page._text_elements["empty_page"] = {}
    page._html = {"empty_page": "<html><body>Something went wrong</body></html>"}

    service, page, context = _build_service(page)

    session_path = tmp_path / "session"
    session_path.mkdir()

    with pytest.raises(BrowserError):
        await service.extract_code(
            session_path, AUTH_URL, fingerprint=_default_fingerprint()
        )

    assert context.closed


# ---------------------------------------------------------------------------
# Debug and cleanup
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test__extract_code__debug_saves_snapshots(tmp_path: Path) -> None:
    """Debug screenshots are saved at each step."""
    page = build_extract_code_scenario(
        auth_code="DEBUG_TEST_CODE_1234567890",
    )
    service, page, _ = _build_service(page, browser_debug=True)

    session_path = tmp_path / "session"
    session_path.mkdir()

    await service.extract_code(
        session_path, AUTH_URL, fingerprint=_default_fingerprint()
    )

    debug_dir = session_path / "debug"
    assert debug_dir.exists()
    assert (debug_dir / "06_auth_page.png").exists()
    assert (debug_dir / "07_after_authorize.png").exists()


@pytest.mark.unit
async def test__extract_code__always_closes_context(tmp_path: Path) -> None:
    """Context is closed even on success."""
    page = build_extract_code_scenario(auth_code="CLOSE_TEST_CODE_123456789")
    service, _, context = _build_service(page)

    session_path = tmp_path / "session"
    session_path.mkdir()

    await service.extract_code(
        session_path, AUTH_URL, fingerprint=_default_fingerprint()
    )

    assert context.closed


@pytest.mark.unit
async def test__extract_code__closes_context_on_error(tmp_path: Path) -> None:
    """Context is closed when extract_code raises."""
    page = FakePage()
    page._url_to_state = {"oauth/authorize": "empty_page"}
    page._css_elements["empty_page"] = {}
    page._text_elements["empty_page"] = {}
    page._html = {"empty_page": "<html></html>"}

    service, _, context = _build_service(page)

    session_path = tmp_path / "session"
    session_path.mkdir()

    with pytest.raises(BrowserError):
        await service.extract_code(
            session_path, AUTH_URL, fingerprint=_default_fingerprint()
        )

    assert context.closed
