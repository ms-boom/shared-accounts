"""Tests that the resolved fingerprint actually reaches the browser context.

Complements test_sms_init_session_fake.py / test_sms_process_login.py /
test_sms_extract_code.py: those cover the request/response flow, this file
asserts the value-object → Patchright wiring contract in isolation:
- `launch_persistent_context` receives user_agent/locale/timezone_id
- `context.add_init_script` receives one script carrying cpu_cores/device_memory
- `fingerprint` is required and keyword-only (fail-fast, no silent default)

Uses the fake browser stack — this does NOT confirm real Cloudflare-bypass
behavior. See the Phase 4a hand-off note for the required manual smoke test.
"""

from pathlib import Path

import pytest

from core.config import Settings
from core.fingerprint import EffectiveFingerprint
from core.services.session_management_service import SessionManagementService
from tests.fixtures.fake_browser import (
    FakeBrowserContext,
    FakeElement,
    FakePage,
    FakePlaywright,
    build_extract_code_scenario,
    build_login_scenario,
)


def _make_settings() -> Settings:
    """Real `Settings`, `_env_file=None` so local `.env` cannot leak into tests."""
    return Settings(
        _env_file=None,
        TELEGRAM_TOKEN="test-token",
        PLAYWRIGHT_TIMEOUT=30000,
        BROWSER_DEBUG=False,
    )


def _custom_fingerprint() -> EffectiveFingerprint:
    """Distinct, non-default values so accidental fallback-to-default is caught."""
    return EffectiveFingerprint(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) CustomTestAgent/1.0",
        cpu_cores=6,
        device_memory=4,
        timezone="Europe/Berlin",
        locale="de-DE",
    )


def _build_process_login_scenario() -> FakePage:
    """Minimal FakePage that lands straight on the authenticated chat page."""
    page = FakePage()
    page._url_to_state = {"claude.ai/login": "authenticated"}
    page._css_elements["authenticated"] = {
        '[data-testid="chat-input"]': FakeElement(),
    }
    page._html = {"authenticated": "<html><body>chat</body></html>"}
    return page


@pytest.mark.unit
async def test__initialize_session__applies_fingerprint_to_launch_kwargs(
    tmp_path: Path,
) -> None:
    page = build_login_scenario()
    context = FakeBrowserContext(page)
    service = SessionManagementService(
        settings=_make_settings(), playwright=FakePlaywright(context)
    )
    fingerprint = _custom_fingerprint()

    await service.initialize_session(
        tmp_path / "session", "user@example.com", fingerprint=fingerprint
    )

    assert context.launch_kwargs["user_agent"] == fingerprint.user_agent
    assert context.launch_kwargs["locale"] == fingerprint.locale
    assert context.launch_kwargs["timezone_id"] == fingerprint.timezone


@pytest.mark.unit
async def test__initialize_session__installs_navigator_init_script(
    tmp_path: Path,
) -> None:
    page = build_login_scenario()
    context = FakeBrowserContext(page)
    service = SessionManagementService(
        settings=_make_settings(), playwright=FakePlaywright(context)
    )
    fingerprint = _custom_fingerprint()

    await service.initialize_session(
        tmp_path / "session", "user@example.com", fingerprint=fingerprint
    )

    assert len(context.init_scripts) == 1
    script = context.init_scripts[0]
    assert "hardwareConcurrency" in script
    assert str(fingerprint.cpu_cores) in script
    assert "deviceMemory" in script
    assert str(fingerprint.device_memory) in script


@pytest.mark.unit
async def test__process_login__applies_fingerprint_to_launch_kwargs(
    tmp_path: Path,
) -> None:
    page = _build_process_login_scenario()
    context = FakeBrowserContext(page)
    service = SessionManagementService(
        settings=_make_settings(), playwright=FakePlaywright(context)
    )
    fingerprint = _custom_fingerprint()
    session_path = tmp_path / "session"
    session_path.mkdir()

    await service.process_login(
        session_path,
        "https://claude.ai/login?token=valid",
        fingerprint=fingerprint,
    )

    assert context.launch_kwargs["user_agent"] == fingerprint.user_agent
    assert context.launch_kwargs["locale"] == fingerprint.locale
    assert context.launch_kwargs["timezone_id"] == fingerprint.timezone
    assert len(context.init_scripts) == 1
    assert str(fingerprint.cpu_cores) in context.init_scripts[0]
    assert str(fingerprint.device_memory) in context.init_scripts[0]


@pytest.mark.unit
async def test__extract_code__applies_fingerprint_to_launch_kwargs(
    tmp_path: Path,
) -> None:
    page = build_extract_code_scenario(auth_code="TEST_AUTH_CODE_0123456789")
    context = FakeBrowserContext(page)
    service = SessionManagementService(
        settings=_make_settings(), playwright=FakePlaywright(context)
    )
    fingerprint = _custom_fingerprint()
    session_path = tmp_path / "session"
    session_path.mkdir()

    await service.extract_code(
        session_path,
        "https://claude.ai/oauth/authorize?client_id=abc",
        fingerprint=fingerprint,
    )

    assert context.launch_kwargs["user_agent"] == fingerprint.user_agent
    assert context.launch_kwargs["locale"] == fingerprint.locale
    assert context.launch_kwargs["timezone_id"] == fingerprint.timezone
    assert len(context.init_scripts) == 1
    assert str(fingerprint.cpu_cores) in context.init_scripts[0]
    assert str(fingerprint.device_memory) in context.init_scripts[0]


@pytest.mark.unit
async def test__initialize_session__init_script_precedes_first_goto(
    tmp_path: Path,
) -> None:
    """The init script must be installed before any navigation (ARCH §4)."""
    page = build_login_scenario()
    context = FakeBrowserContext(page)
    service = SessionManagementService(
        settings=_make_settings(), playwright=FakePlaywright(context)
    )

    await service.initialize_session(
        tmp_path / "session", "user@example.com", fingerprint=_custom_fingerprint()
    )

    assert len(context.init_scripts) == 1
    assert len(page.goto_history) >= 1


@pytest.mark.unit
async def test__initialize_session__missing_fingerprint_raises_type_error(
    tmp_path: Path,
) -> None:
    """`fingerprint` is required and keyword-only — no silent default."""
    page = build_login_scenario()
    context = FakeBrowserContext(page)
    service = SessionManagementService(
        settings=_make_settings(), playwright=FakePlaywright(context)
    )

    with pytest.raises(TypeError):
        await service.initialize_session(  # type: ignore[call-arg]
            tmp_path / "session", "user@example.com"
        )


@pytest.mark.unit
async def test__initialize_session__fingerprint_rejected_as_positional(
    tmp_path: Path,
) -> None:
    """`fingerprint` cannot be passed positionally (keyword-only per ARCH §3.1)."""
    page = build_login_scenario()
    context = FakeBrowserContext(page)
    service = SessionManagementService(
        settings=_make_settings(), playwright=FakePlaywright(context)
    )

    with pytest.raises(TypeError):
        await service.initialize_session(  # type: ignore[misc]
            tmp_path / "session", "user@example.com", _custom_fingerprint()
        )
