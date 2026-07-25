"""Fake browser objects for testing SessionManagementService.

Provides FakePage, FakeBrowserContext, FakePlaywright that simulate
real browser behavior through a state machine, replacing fragile mocks.

State machine approach: FakePage holds named states. Each state defines
which CSS selectors and text patterns exist. Locators resolve lazily
against the page's current state, so state transitions (e.g. click)
affect subsequent locator operations naturally.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from patchright.async_api import TimeoutError as PlaywrightTimeoutError

# ---------------------------------------------------------------------------
# HTML fixtures (minimal anonymized versions of real Claude pages)
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).parent / "html"


def _load_html(filename: str) -> str:
    return (_FIXTURES_DIR / filename).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Element configuration
# ---------------------------------------------------------------------------


@dataclass
class FakeElement:
    """Describes element behavior in a page state."""

    exists: bool = True
    text: str = ""
    value: str = ""
    on_click_goto_state: str | None = None
    on_fill_store_as: str | None = None


# ---------------------------------------------------------------------------
# FakeLocator
# ---------------------------------------------------------------------------


class FakeLocator:
    """Fake Playwright Locator resolved lazily against FakePage state."""

    def __init__(
        self,
        page: FakePage,
        queries: list[tuple[str, str]],
    ) -> None:
        self._page = page
        self._queries = queries  # [(kind, pattern), ...]

    def or_(self, other: FakeLocator) -> FakeLocator:
        return FakeLocator(self._page, self._queries + other._queries)

    @property
    def first(self) -> FakeLocator:
        return self

    def _resolve(self) -> FakeElement | None:
        """Find first matching element in page's current state."""
        for kind, pattern in self._queries:
            registry = (
                self._page._css_elements if kind == "css" else self._page._text_elements
            )
            state_elements = registry.get(self._page.state, {})
            for key, elem in state_elements.items():
                if key in pattern or pattern in key:
                    if elem.exists:
                        return elem
        return None

    async def click(self, timeout: int = 30000) -> None:
        elem = self._resolve()
        if elem is None:
            raise PlaywrightTimeoutError(f"Timeout: {self._queries}")
        if elem.on_click_goto_state:
            self._page.state = elem.on_click_goto_state

    async def fill(self, value: str, timeout: int = 30000) -> None:
        elem = self._resolve()
        if elem is None:
            raise PlaywrightTimeoutError(f"Timeout: {self._queries}")
        if elem.on_fill_store_as:
            self._page.filled[elem.on_fill_store_as] = value

    async def wait_for(self, timeout: int = 30000, state: str = "visible") -> None:
        elem = self._resolve()
        if elem is None:
            raise PlaywrightTimeoutError(f"Timeout: {self._queries}")

    async def text_content(self) -> str | None:
        elem = self._resolve()
        return elem.text if elem else None

    async def get_attribute(self, name: str) -> str | None:
        elem = self._resolve()
        if elem and name == "value":
            return elem.value
        return None


# ---------------------------------------------------------------------------
# FakePage
# ---------------------------------------------------------------------------


class FakePage:
    """Fake browser page with state machine."""

    def __init__(self) -> None:
        self.state: str = "blank"
        self._url_to_state: dict[str, str] = {}
        self._css_elements: dict[str, dict[str, FakeElement]] = {}
        self._text_elements: dict[str, dict[str, FakeElement]] = {}
        self._html: dict[str, str] = {}
        self._goto_error: Exception | None = None
        self.goto_history: list[str] = []
        self.filled: dict[str, str] = {}
        self.screenshot_paths: list[str] = []
        self.init_scripts: list[str] = []

    async def add_init_script(self, script: str) -> None:
        self.init_scripts.append(script)

    async def goto(self, url: str, **kwargs: object) -> None:
        if self._goto_error:
            raise self._goto_error
        self.goto_history.append(url)
        for pattern, target_state in self._url_to_state.items():
            if pattern in url:
                self.state = target_state
                return

    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator(self, [("css", selector)])

    def get_by_text(self, text: str, exact: bool = True) -> FakeLocator:
        return FakeLocator(self, [("text", text)])

    async def content(self) -> str:
        return self._html.get(self.state, "<html><body></body></html>")

    async def screenshot(self, **kwargs: object) -> None:
        path = kwargs.get("path", "")
        if path:
            self.screenshot_paths.append(str(path))
            Path(str(path)).parent.mkdir(parents=True, exist_ok=True)
            Path(str(path)).write_bytes(b"FAKE_PNG")

    async def wait_for_load_state(self, state: str = "load") -> None:
        pass

    def expect_navigation(self, **kwargs: object) -> _FakeNavigationContext:
        """Fake async context manager for page.expect_navigation()."""
        return _FakeNavigationContext()


class _FakeNavigationContext:
    """Async context manager that does nothing (navigation happens via state machine)."""

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *args: object) -> bool:
        return False


# ---------------------------------------------------------------------------
# FakeBrowserContext & FakePlaywright
# ---------------------------------------------------------------------------


class FakeBrowserContext:
    """Fake Playwright BrowserContext."""

    def __init__(self, page: FakePage) -> None:
        self.pages: list[FakePage] = [page]
        self.closed = False
        self.launch_kwargs: dict[str, object] = {}
        self.init_scripts: list[str] = []

    async def new_page(self) -> FakePage:
        return self.pages[0]

    async def close(self) -> None:
        self.closed = True

    async def add_init_script(self, script: str) -> None:
        self.init_scripts.append(script)


class FakePlaywright:
    """Fake Playwright instance."""

    def __init__(self, context: FakeBrowserContext) -> None:
        self.chromium = _FakeChromium(context)


class _FakeChromium:
    def __init__(self, context: FakeBrowserContext) -> None:
        self._context = context

    async def launch_persistent_context(self, **kwargs: object) -> FakeBrowserContext:
        self._context.launch_kwargs = dict(kwargs)
        return self._context


# ---------------------------------------------------------------------------
# Scenario builders
# ---------------------------------------------------------------------------


def build_login_scenario(
    *,
    has_cookie_popup: bool = True,
    confirmation_type: str = "check_email",
) -> FakePage:
    """Build FakePage for initialize_session scenario.

    Args:
        has_cookie_popup: Whether cookie consent banner is shown.
        confirmation_type: What appears after email submit:
            "check_email" — text confirmation (default)
            "verification_code" — code input field
            "none" — nothing appears (simulates timeout)
    """
    page = FakePage()

    page._url_to_state = {"claude.ai/login": "login_page"}

    # -- Login page state --
    login_css: dict[str, FakeElement] = {}
    if has_cookie_popup:
        login_css["Reject All Cookies"] = FakeElement()
    login_css['input[type="email"]'] = FakeElement(on_fill_store_as="email")
    login_css["Continue with email"] = FakeElement(
        on_click_goto_state="email_sent",
    )
    page._css_elements["login_page"] = login_css

    # -- Email sent state --
    if confirmation_type == "check_email":
        page._text_elements["email_sent"] = {
            "Check your email": FakeElement(text="Check your email"),
        }
    elif confirmation_type == "verification_code":
        page._css_elements["email_sent"] = {
            'input[name="code"]': FakeElement(),
        }
    # "none" → no elements registered → locators will timeout

    # -- HTML fixtures --
    page._html = {
        "login_page": _load_html("01_login_page.html"),
        "email_sent": _load_html("02_after_submit.html"),
    }

    return page


def build_extract_code_scenario(
    *,
    has_authorize_button: bool = True,
    auth_code: str = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9_fakecode",
    has_cookie_popup: bool = False,
) -> FakePage:
    """Build FakePage for extract_code scenario (OAuth consent -> code page).

    Matches real Claude flow: "Authentication Code" heading + code in <pre> tag.

    Args:
        has_authorize_button: Whether OAuth consent screen has Authorize button.
        auth_code: Authorization code displayed in <pre> tag after authorization.
        has_cookie_popup: Whether cookie consent banner is shown.
    """
    page = FakePage()

    page._url_to_state = {"oauth/authorize": "consent_screen"}

    # -- Consent screen state --
    consent_css: dict[str, FakeElement] = {}
    if has_cookie_popup:
        consent_css["Reject All Cookies"] = FakeElement()
    if has_authorize_button:
        consent_css["Authorize"] = FakeElement(
            on_click_goto_state="code_page",
        )
    page._css_elements["consent_screen"] = consent_css

    # -- Code page state (after Authorize click) --
    # "Authentication Code" heading found via get_by_text()
    page._text_elements["code_page"] = {
        "Authentication Code": FakeElement(text="Authentication Code"),
    }
    # Code lives in a <pre> tag, found via locator("pre")
    page._css_elements["code_page"] = {
        "pre": FakeElement(text=auth_code),
    }

    # -- HTML fixtures --
    page._html = {
        "consent_screen": _load_html("06_auth_page.html"),
        "code_page": _load_html("07_after_authorize.html"),
    }

    return page
