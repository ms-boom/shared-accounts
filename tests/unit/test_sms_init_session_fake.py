"""Tests for SessionManagementService.initialize_session() using Fake browser.

Uses FakePage state machine instead of mocks for readable, scenario-based tests.
"""

from pathlib import Path

import pytest

from core.config import Settings
from core.exceptions import BrowserError
from core.fingerprint import EffectiveFingerprint
from core.services.session_management_service import SessionManagementService
from tests.fixtures.fake_browser import (
    FakeBrowserContext,
    FakePlaywright,
    build_login_scenario,
)


def _make_settings(timeout: int = 30000, browser_debug: bool = False) -> Settings:
    """Real `Settings`, `_env_file=None` so local `.env` cannot leak into tests."""
    return Settings(
        _env_file=None,
        TELEGRAM_TOKEN="test-token",
        PLAYWRIGHT_TIMEOUT=timeout,
        BROWSER_DEBUG=browser_debug,
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


def _build_service(
    page=None,
    *,
    has_cookie_popup: bool = True,
    confirmation_type: str = "check_email",
    browser_debug: bool = False,
):
    """Build service + fake browser stack. Returns (service, page, context)."""
    if page is None:
        page = build_login_scenario(
            has_cookie_popup=has_cookie_popup,
            confirmation_type=confirmation_type,
        )
    context = FakeBrowserContext(page)
    playwright = FakePlaywright(context)
    service = SessionManagementService(
        settings=_make_settings(browser_debug=browser_debug),
        playwright=playwright,
    )
    return service, page, context


# -----------------------------------------------------------------------
# Happy path
# -----------------------------------------------------------------------


@pytest.mark.unit
async def test__init_session__happy_path__returns_email_sent_message(
    tmp_path: Path,
) -> None:
    """Full flow: goto login → fill email → click continue → confirmation."""
    service, page, context = _build_service()
    session_path = tmp_path / "session"
    session_path.mkdir()

    result = await service.initialize_session(
        session_path, "user@example.com", fingerprint=_default_fingerprint()
    )

    assert "Email sent" in result
    assert "authorization link" in result


@pytest.mark.unit
async def test__init_session__fills_provided_email(tmp_path: Path) -> None:
    service, page, _ = _build_service()
    session_path = tmp_path / "session"
    session_path.mkdir()

    await service.initialize_session(
        session_path, "test@example.com", fingerprint=_default_fingerprint()
    )

    assert page.filled["email"] == "test@example.com"


@pytest.mark.unit
async def test__init_session__navigates_to_login_page(tmp_path: Path) -> None:
    service, page, _ = _build_service()
    session_path = tmp_path / "session"
    session_path.mkdir()

    await service.initialize_session(
        session_path, "user@example.com", fingerprint=_default_fingerprint()
    )

    assert any("claude.ai/login" in url for url in page.goto_history)


@pytest.mark.unit
async def test__init_session__transitions_to_email_sent_state(
    tmp_path: Path,
) -> None:
    """After clicking 'Continue with email', page state becomes email_sent."""
    service, page, _ = _build_service()
    session_path = tmp_path / "session"
    session_path.mkdir()

    await service.initialize_session(
        session_path, "user@example.com", fingerprint=_default_fingerprint()
    )

    assert page.state == "email_sent"


# -----------------------------------------------------------------------
# Cookie popup variations
# -----------------------------------------------------------------------


@pytest.mark.unit
async def test__init_session__dismisses_cookie_popup(tmp_path: Path) -> None:
    """Cookie popup is present and gets dismissed without error."""
    service, _, _ = _build_service(has_cookie_popup=True)
    session_path = tmp_path / "session"
    session_path.mkdir()

    result = await service.initialize_session(
        session_path, "user@example.com", fingerprint=_default_fingerprint()
    )

    assert "Email sent" in result


@pytest.mark.unit
async def test__init_session__no_cookie_popup__still_succeeds(
    tmp_path: Path,
) -> None:
    """No cookie popup — silently skipped via PlaywrightTimeoutError catch."""
    service, _, _ = _build_service(has_cookie_popup=False)
    session_path = tmp_path / "session"
    session_path.mkdir()

    result = await service.initialize_session(
        session_path, "user@example.com", fingerprint=_default_fingerprint()
    )

    assert "Email sent" in result


# -----------------------------------------------------------------------
# Confirmation variants
# -----------------------------------------------------------------------


@pytest.mark.unit
async def test__init_session__verification_code_variant__returns_success(
    tmp_path: Path,
) -> None:
    """Claude shows verification code input instead of 'Check your email'."""
    service, _, _ = _build_service(confirmation_type="verification_code")
    session_path = tmp_path / "session"
    session_path.mkdir()

    result = await service.initialize_session(
        session_path, "user@example.com", fingerprint=_default_fingerprint()
    )

    assert "Email sent" in result


@pytest.mark.unit
async def test__init_session__timeout_waiting_for_confirmation(
    tmp_path: Path,
) -> None:
    """No confirmation appears — BrowserError raised."""
    service, _, _ = _build_service(confirmation_type="none")
    session_path = tmp_path / "session"
    session_path.mkdir()

    with pytest.raises(BrowserError, match="timed out"):
        await service.initialize_session(
            session_path, "user@example.com", fingerprint=_default_fingerprint()
        )


# -----------------------------------------------------------------------
# Error handling
# -----------------------------------------------------------------------


@pytest.mark.unit
async def test__init_session__timeout_on_page_load__raises_browser_error(
    tmp_path: Path,
) -> None:
    from patchright.async_api import TimeoutError as PlaywrightTimeoutError

    page = build_login_scenario()
    page._goto_error = PlaywrightTimeoutError("page load timeout")
    service, _, _ = _build_service(page=page)
    session_path = tmp_path / "session"
    session_path.mkdir()

    with pytest.raises(BrowserError, match="timed out"):
        await service.initialize_session(
            session_path, "user@example.com", fingerprint=_default_fingerprint()
        )


@pytest.mark.unit
async def test__init_session__generic_error__raises_browser_error(
    tmp_path: Path,
) -> None:
    page = build_login_scenario()
    page._goto_error = RuntimeError("network failure")
    service, _, _ = _build_service(page=page)
    session_path = tmp_path / "session"
    session_path.mkdir()

    with pytest.raises(BrowserError, match="Failed to initialize session"):
        await service.initialize_session(
            session_path, "user@example.com", fingerprint=_default_fingerprint()
        )


# -----------------------------------------------------------------------
# Context lifecycle
# -----------------------------------------------------------------------


@pytest.mark.unit
async def test__init_session__always_closes_context(tmp_path: Path) -> None:
    service, _, context = _build_service()
    session_path = tmp_path / "session"
    session_path.mkdir()

    await service.initialize_session(
        session_path, "user@example.com", fingerprint=_default_fingerprint()
    )

    assert context.closed


@pytest.mark.unit
async def test__init_session__closes_context_on_error(tmp_path: Path) -> None:
    from patchright.async_api import TimeoutError as PlaywrightTimeoutError

    page = build_login_scenario()
    page._goto_error = PlaywrightTimeoutError("timeout")
    service, _, context = _build_service(page=page)
    session_path = tmp_path / "session"
    session_path.mkdir()

    with pytest.raises(BrowserError):
        await service.initialize_session(
            session_path, "user@example.com", fingerprint=_default_fingerprint()
        )

    assert context.closed


# -----------------------------------------------------------------------
# Debug snapshots
# -----------------------------------------------------------------------


@pytest.mark.unit
async def test__init_session__debug_enabled__saves_snapshots(
    tmp_path: Path,
) -> None:
    service, page, _ = _build_service(browser_debug=True)
    session_path = tmp_path / "session"
    session_path.mkdir()

    await service.initialize_session(
        session_path, "user@example.com", fingerprint=_default_fingerprint()
    )

    debug_dir = session_path / "debug"
    assert debug_dir.exists()
    assert (debug_dir / "01_login_page.png").exists()
    assert (debug_dir / "02_after_submit.png").exists()
    assert (debug_dir / "03_after_wait.png").exists()
    # HTML snapshots also saved
    assert (debug_dir / "01_login_page.html").exists()


@pytest.mark.unit
async def test__init_session__debug_disabled__skips_snapshots(
    tmp_path: Path,
) -> None:
    service, page, _ = _build_service(browser_debug=False)
    session_path = tmp_path / "session"
    session_path.mkdir()

    await service.initialize_session(
        session_path, "user@example.com", fingerprint=_default_fingerprint()
    )

    assert len(page.screenshot_paths) == 0


@pytest.mark.unit
async def test__init_session__debug_disabled__saves_error_snapshots(
    tmp_path: Path,
) -> None:
    """Error snapshots are always saved regardless of BROWSER_DEBUG."""
    service, _, _ = _build_service(confirmation_type="none", browser_debug=False)
    session_path = tmp_path / "session"
    session_path.mkdir()

    with pytest.raises(BrowserError):
        await service.initialize_session(
            session_path, "user@example.com", fingerprint=_default_fingerprint()
        )

    debug_dir = session_path / "debug"
    assert (debug_dir / "error_init.png").exists()


# -----------------------------------------------------------------------
# Session path creation
# -----------------------------------------------------------------------


@pytest.mark.unit
async def test__init_session__creates_session_directory(
    tmp_path: Path,
) -> None:
    """Session path is created by _create_persistent_context."""
    service, _, _ = _build_service()
    session_path = tmp_path / "new_session"
    # Directory does NOT exist yet

    await service.initialize_session(
        session_path, "user@example.com", fingerprint=_default_fingerprint()
    )

    assert session_path.exists()
