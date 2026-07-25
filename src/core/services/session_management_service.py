"""Session management service for Claude sessions using Patchright."""

import logging
from pathlib import Path

from patchright.async_api import (
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
)

from core.config import Settings
from core.exceptions import BrowserError, SessionError
from core.fingerprint import EffectiveFingerprint, build_navigator_init_script

logger = logging.getLogger(__name__)


class SessionManagementService:
    """
    Service for managing Claude sessions.

    Provides session initialization, login processing, and code extraction
    using Patchright browser automation with persistent contexts.
    Persistent contexts store cookies/state in user_data_dir automatically,
    which also helps bypass Cloudflare Turnstile detection.
    """

    def __init__(self, settings: Settings, playwright: Playwright):
        self.settings = settings
        self.playwright = playwright

    async def _create_persistent_context(
        self, session_path: Path, fingerprint: EffectiveFingerprint
    ) -> BrowserContext:
        """
        Create a persistent browser context for the given session path.

        Persistent context stores all cookies, localStorage, and browser state
        in user_data_dir. This avoids manual storage_state management and
        presents a consistent browser fingerprint to Cloudflare.

        The resolved fingerprint's user_agent/locale/timezone are applied as
        launch kwargs; cpu_cores/device_memory are applied via an init script
        installed before any navigation, so every subsequent `goto` on this
        context's page observes the overridden `navigator` properties.
        """
        session_path.mkdir(parents=True, exist_ok=True, mode=0o700)

        # Remove stale lock file left after container restart or crash.
        # Chrome creates SingletonLock tied to the host process; after
        # container recreation the PID/hostname changes but the volume persists.
        singleton_lock = session_path / "SingletonLock"
        if singleton_lock.exists():
            singleton_lock.unlink()
            logger.warning("Removed stale SingletonLock from %s", session_path)

        context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(session_path),
            channel="chrome",
            headless=self.settings.PLAYWRIGHT_HEADLESS,
            no_viewport=True,
            args=["--window-size=1920,1080"],
            ignore_default_args=["--enable-automation"],
            user_agent=fingerprint.user_agent,
            locale=fingerprint.locale,
            timezone_id=fingerprint.timezone,
        )
        await context.add_init_script(
            build_navigator_init_script(
                fingerprint.cpu_cores, fingerprint.device_memory
            )
        )
        return context

    async def _save_debug(self, page: Page, session_path: Path, step_name: str) -> None:
        """Save screenshot and HTML for debugging."""
        is_error = step_name.startswith("error_")
        if not is_error and not self.settings.BROWSER_DEBUG:
            return

        debug_dir = session_path / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)

        try:
            await page.screenshot(
                path=str(debug_dir / f"{step_name}.png"),
                full_page=True,
            )
            html = await page.content()
            (debug_dir / f"{step_name}.html").write_text(html, encoding="utf-8")
            logger.debug(f"Saved debug snapshot: {step_name}")
        except Exception as e:
            logger.warning(f"Failed to save debug snapshot {step_name}: {e}")

    async def _dismiss_cookie_popup(self, page: Page) -> None:
        """Dismiss cookie consent popup if present."""
        try:
            reject_btn = page.locator(
                'button:has-text("Reject All Cookies"), '
                'button:has-text("Accept All Cookies")'
            ).first
            await reject_btn.click(timeout=3000)
            logger.info("Dismissed cookie popup")
        except PlaywrightTimeoutError:
            pass

    async def initialize_session(
        self, session_path: Path, email: str, *, fingerprint: EffectiveFingerprint
    ) -> str:
        """
        Initialize Claude session at specific path.

        Opens login page, fills email, submits. Waits for either
        verification code input or "Check your email" confirmation.

        Args:
            session_path: Path to the Playwright session directory
            email: Email address for Claude account
            fingerprint: Resolved fingerprint applied to the browser context
        """
        context: BrowserContext | None = None
        page: Page | None = None

        try:
            context = await self._create_persistent_context(session_path, fingerprint)
            page = context.pages[0] if context.pages else await context.new_page()

            await page.goto(
                "https://claude.ai/login",
                timeout=self.settings.PLAYWRIGHT_TIMEOUT,
                wait_until="domcontentloaded",
            )
            logger.info(f"Opened login page for session {session_path}")
            await self._save_debug(page, session_path, "01_login_page")

            await self._dismiss_cookie_popup(page)

            email_input = page.locator('input[type="email"]')
            await email_input.fill(email, timeout=self.settings.PLAYWRIGHT_TIMEOUT)
            logger.info(f"Filled email for session {session_path}")

            continue_button = page.locator('button:has-text("Continue with email")')
            await continue_button.click()
            await self._save_debug(page, session_path, "02_after_submit")

            # Claude shows either verification code input or "Check your email"
            code_input = page.locator(
                'input[name="code"], '
                'input[placeholder*="verification"], '
                'input[placeholder*="code"]'
            )
            confirmation_text = (
                page.get_by_text("Check your email")
                .or_(page.get_by_text("verification code"))
                .or_(page.get_by_text("Verify"))
            )
            combined = code_input.or_(confirmation_text)
            try:
                await combined.first.wait_for(
                    timeout=self.settings.PLAYWRIGHT_TIMEOUT,
                )
            except PlaywrightTimeoutError:
                await self._save_debug(page, session_path, "02_timeout")
                raise

            await self._save_debug(page, session_path, "03_after_wait")
            logger.info(f"Email sent confirmation for session {session_path}")

            return (
                "📧 Email sent! Please reply to this message with "
                "the authorization link from your inbox."
            )

        except PlaywrightTimeoutError as e:
            logger.error(f"Timeout during session init for {session_path}: {e}")
            if page:
                await self._save_debug(page, session_path, "error_init")
            raise BrowserError(
                "❌ Operation timed out. The page took too long to respond."
            ) from e
        except Exception as e:
            logger.error(f"Failed to initialize session at {session_path}: {e}")
            if page:
                await self._save_debug(page, session_path, "error_init")
            raise BrowserError(f"❌ Failed to initialize session: {str(e)}") from e
        finally:
            if context:
                await context.close()

    async def process_login(
        self, session_path: Path, login_url: str, *, fingerprint: EffectiveFingerprint
    ) -> str:
        """
        Process Claude login link to complete authentication.

        Opens the magic link URL in persistent context, then verifies
        the session by navigating to /settings/usage.

        Args:
            session_path: Path to the Playwright session directory
            login_url: Login URL from email
            fingerprint: Resolved fingerprint applied to the browser context
        """
        if not session_path.exists():
            raise SessionError(
                f"❌ No session found at {session_path}. Run init-session first."
            )

        context: BrowserContext | None = None
        page: Page | None = None

        try:
            context = await self._create_persistent_context(session_path, fingerprint)
            page = context.pages[0] if context.pages else await context.new_page()

            # Step 1: Open magic link
            try:
                await page.goto(
                    login_url,
                    timeout=self.settings.PLAYWRIGHT_TIMEOUT,
                    wait_until="domcontentloaded",
                )
            except PlaywrightTimeoutError as e:
                logger.error(f"Timeout loading magic link for {session_path}: {e}")
                if page:
                    await self._save_debug(page, session_path, "error_login")
                raise BrowserError(
                    "❌ Login link is invalid or expired. "
                    "Please run init-session again."
                ) from e
            await self._save_debug(page, session_path, "04_magic_link")

            await self._dismiss_cookie_popup(page)

            # Step 2: Verify authentication — wait for chat input
            # After successful login, Claude redirects to the main page
            # with the chat input form (data-testid="chat-input").
            chat_input = page.locator('[data-testid="chat-input"]')
            await chat_input.first.wait_for(
                timeout=self.settings.PLAYWRIGHT_TIMEOUT,
                state="visible",
            )
            await self._save_debug(page, session_path, "05_authenticated")
            logger.info(f"Authentication successful for session {session_path}")

            return "✅ Session initialized successfully! You can now use /get_code."

        except PlaywrightTimeoutError as e:
            logger.error(f"Timeout verifying session for {session_path}: {e}")
            if page:
                await self._save_debug(page, session_path, "error_login")
            raise BrowserError(
                "❌ Session verification timed out. "
                "Login may have succeeded — check debug screenshots."
            ) from e
        except BrowserError:
            raise
        except Exception as e:
            logger.error(f"Failed to process login link for {session_path}: {e}")
            if page:
                await self._save_debug(page, session_path, "error_login")
            raise BrowserError(f"❌ Failed to process login link: {str(e)}") from e
        finally:
            if context:
                await context.close()

    async def extract_code(
        self, session_path: Path, auth_url: str, *, fingerprint: EffectiveFingerprint
    ) -> str:
        """
        Extract authorization code from Claude authorization page.

        Args:
            session_path: Path to the Playwright session directory
            auth_url: Authorization URL from Claude Code
            fingerprint: Resolved fingerprint applied to the browser context
        """
        if not session_path.exists():
            raise SessionError(
                f"❌ No active session found at {session_path}. Run init-session first."
            )

        context: BrowserContext | None = None
        page: Page | None = None

        try:
            context = await self._create_persistent_context(session_path, fingerprint)
            page = context.pages[0] if context.pages else await context.new_page()

            await page.goto(
                auth_url,
                timeout=self.settings.PLAYWRIGHT_TIMEOUT,
                wait_until="domcontentloaded",
            )
            await self._save_debug(page, session_path, "06_auth_page")

            await self._dismiss_cookie_popup(page)

            # Click "Authorize" button if present (OAuth consent screen)
            authorize_btn = page.locator('button:has-text("Authorize")')
            try:
                await authorize_btn.wait_for(timeout=5000, state="visible")
                async with page.expect_navigation(
                    timeout=self.settings.PLAYWRIGHT_TIMEOUT,
                    wait_until="domcontentloaded",
                ):
                    await authorize_btn.click()
                logger.info(f"Clicked Authorize button for {session_path}")
                await self._save_debug(page, session_path, "07_after_authorize")
            except PlaywrightTimeoutError:
                # No Authorize button or no navigation after click
                logger.debug("No Authorize button found, looking for code directly")

            # Wait for "Authentication Code" heading, then extract from <pre>
            heading = page.get_by_text("Authentication Code")
            await heading.wait_for(
                timeout=self.settings.PLAYWRIGHT_TIMEOUT,
                state="visible",
            )

            code_element = page.locator("pre").first
            await code_element.wait_for(
                timeout=5000,
                state="visible",
            )

            code = await code_element.text_content()
            if not code or len(code.strip()) < 20:
                await self._save_debug(page, session_path, "07_no_code_found")
                raise BrowserError("Authorization code element is empty")

            logger.info(f"Extracted code for session {session_path}")
            assert isinstance(code, str)
            return code.strip()

        except PlaywrightTimeoutError as e:
            logger.error(f"Timeout extracting code for {session_path}: {e}")
            if page:
                await self._save_debug(page, session_path, "error_extract")
            raise BrowserError(
                "❌ Operation timed out. Could not extract authorization code."
            ) from e
        except SessionError:
            raise
        except Exception as e:
            logger.error(f"Failed to extract code for {session_path}: {e}")
            if page:
                await self._save_debug(page, session_path, "error_extract")

            if "401" in str(e) or "403" in str(e) or "unauthorized" in str(e).lower():
                raise SessionError(
                    f"❌ Session expired or invalid at {session_path}. "
                    "Please run init-session again."
                ) from e

            raise BrowserError(
                f"❌ Could not extract authorization code: {str(e)}"
            ) from e
        finally:
            if context:
                await context.close()
