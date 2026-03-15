"""Session management service for Claude sessions."""

import logging
from pathlib import Path

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeoutError,
)

from core.config import Settings
from core.exceptions import BrowserError, SessionError

logger = logging.getLogger(__name__)


class SessionManagementService:
    """
    Service for managing Claude sessions.

    Provides session initialization, login processing, and code extraction
    using Playwright browser automation. Works with session paths directly.
    """

    def __init__(self, settings: Settings, browser: Browser):
        """
        Initialize session management service.

        Args:
            settings: Application settings
            browser: Playwright browser instance
        """
        self.settings = settings
        self.browser = browser

    async def initialize_session(self, session_path: Path, email: str) -> str:
        """
        Initialize Claude session at specific path.

        Opens login page, fills email, requests login link.

        Args:
            session_path: Path to store session data
            email: Email address for Claude account

        Returns:
            Success message

        Raises:
            BrowserError: If browser operation fails
        """
        session_path.mkdir(parents=True, exist_ok=True, mode=0o700)

        context: BrowserContext | None = None
        page: Page | None = None

        try:
            context = await self.browser.new_context(
                storage_state=None,
                viewport={"width": 1280, "height": 720},
            )

            page = await context.new_page()

            # Navigate to Claude login page
            await page.goto(
                "https://claude.ai/login",
                timeout=self.settings.PLAYWRIGHT_TIMEOUT,
            )
            logger.info(f"Opened login page for session {session_path}")

            # Fill email field
            email_input = page.locator('input[type="email"]')
            await email_input.fill(email)
            logger.info(f"Filled email for session {session_path}")

            # Click "Continue with email" button
            continue_button = page.locator('button:has-text("Continue with email")')
            await continue_button.click()

            # Wait for "Check your email" message
            await page.wait_for_selector(
                'text="Check your email"',
                timeout=self.settings.PLAYWRIGHT_TIMEOUT,
            )
            logger.info(f"Email sent confirmation for session {session_path}")

            # Save session state
            await context.storage_state(path=str(session_path / "state.json"))

            return (
                "📧 Email sent! Please send me the authorization link from your inbox."
            )

        except PlaywrightTimeoutError as e:
            logger.error(f"Timeout during session init for {session_path}: {e}")
            if page:
                screenshot_path = session_path / "error_init.png"
                await page.screenshot(path=str(screenshot_path))
            raise BrowserError(
                "❌ Operation timed out. The page took too long to respond."
            ) from e
        except Exception as e:
            logger.error(f"Failed to initialize session at {session_path}: {e}")
            raise BrowserError(f"❌ Failed to initialize session: {str(e)}") from e
        finally:
            if context:
                await context.close()

    async def process_login(self, session_path: Path, login_url: str) -> str:
        """
        Process Claude login link to complete authentication.

        Args:
            session_path: Path to session directory
            login_url: Login URL from email

        Returns:
            Success message

        Raises:
            SessionError: If session doesn't exist
            BrowserError: If browser operation fails
        """
        state_file = session_path / "state.json"
        if not state_file.exists():
            raise SessionError(
                f"❌ No session found at {session_path}. Run init-session first."
            )

        context: BrowserContext | None = None
        page: Page | None = None

        try:
            context = await self.browser.new_context(
                storage_state=str(state_file),
            )

            page = await context.new_page()

            # Open login link
            await page.goto(login_url, timeout=self.settings.PLAYWRIGHT_TIMEOUT)

            # Wait for successful authentication
            await page.wait_for_selector(
                'button[aria-label="User menu"], [data-testid="user-menu"]',
                timeout=self.settings.PLAYWRIGHT_TIMEOUT,
                state="visible",
            )
            logger.info(f"Authentication successful for session {session_path}")

            # Save authenticated session
            await context.storage_state(path=str(state_file))

            return "✅ Session initialized successfully! You can now use /get_code."

        except PlaywrightTimeoutError as e:
            logger.error(f"Timeout during login for {session_path}: {e}")
            if page:
                screenshot_path = session_path / "error_login.png"
                await page.screenshot(path=str(screenshot_path))
            raise BrowserError(
                "❌ Login link is invalid or expired. Please run init-session again."
            ) from e
        except Exception as e:
            logger.error(f"Failed to process login link for {session_path}: {e}")
            raise BrowserError(f"❌ Failed to process login link: {str(e)}") from e
        finally:
            if context:
                await context.close()

    async def extract_code(self, session_path: Path, auth_url: str) -> str:
        """
        Extract authorization code from Claude authorization page.

        Args:
            session_path: Path to session directory
            auth_url: Authorization URL from Claude Code

        Returns:
            Authorization code

        Raises:
            SessionError: If session doesn't exist or is invalid
            BrowserError: If code extraction fails
        """
        state_file = session_path / "state.json"
        if not state_file.exists():
            raise SessionError(
                f"❌ No active session found at {session_path}. Run init-session first."
            )

        context: BrowserContext | None = None
        page: Page | None = None

        try:
            context = await self.browser.new_context(
                storage_state=str(state_file),
            )

            page = await context.new_page()

            # Navigate to authorization URL
            await page.goto(auth_url, timeout=self.settings.PLAYWRIGHT_TIMEOUT)

            # Wait for authorization code element
            code_element = None
            selectors = [
                "code",
                '[data-testid="auth-code"]',
                'input[name="code"]',
                "div.auth-code",
                "pre.code",
            ]

            for selector in selectors:
                try:
                    code_element = page.locator(selector).first
                    await code_element.wait_for(
                        timeout=5000,
                        state="visible",
                    )
                    break
                except PlaywrightTimeoutError:
                    continue

            if not code_element:
                # Try to find any code-like text
                await page.wait_for_load_state("networkidle")
                code_text = await page.locator(
                    "text=/^[A-Z0-9]{8,}$/"
                ).first.text_content()

                if code_text:
                    logger.info(f"Extracted code for session {session_path}")
                    assert isinstance(code_text, str)  # guarded by if code_text above
                    return code_text.strip()
                else:
                    raise BrowserError("Could not find authorization code on page")

            # Extract code text
            code = await code_element.text_content()
            if not code:
                code = await code_element.get_attribute("value")

            if not code:
                raise BrowserError("Authorization code element is empty")

            logger.info(f"Extracted code for session {session_path}")
            assert isinstance(code, str)  # guarded by if not code checks above
            return code.strip()

        except PlaywrightTimeoutError as e:
            logger.error(f"Timeout extracting code for {session_path}: {e}")
            if page:
                screenshot_path = session_path / "error_extract.png"
                await page.screenshot(path=str(screenshot_path))
            raise BrowserError(
                "❌ Operation timed out. Could not extract authorization code."
            ) from e
        except SessionError:
            raise
        except Exception as e:
            logger.error(f"Failed to extract code for {session_path}: {e}")

            # Check if session is invalid
            if "401" in str(e) or "403" in str(e) or "unauthorized" in str(e).lower():
                if state_file.exists():
                    state_file.unlink()
                raise SessionError(
                    f"❌ Session expired or invalid at {session_path}. Please run init-session again."
                ) from e

            raise BrowserError(
                f"❌ Could not extract authorization code: {str(e)}"
            ) from e
        finally:
            if context:
                await context.close()
