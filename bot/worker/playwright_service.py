"""Playwright automation service for Claude.ai interactions."""

import logging

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

from bot.core.config import Settings
from bot.core.exceptions import BrowserError, SessionError

logger = logging.getLogger(__name__)


class PlaywrightService:
    """
    Service for automating Claude.ai interactions with Playwright.

    Manages browser sessions, handles authentication, and extracts authorization codes.
    """

    def __init__(self, settings: Settings):
        """
        Initialize Playwright service.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.playwright: Playwright | None = None
        self.browser: Browser | None = None

    async def start(self) -> None:
        """Start Playwright and browser."""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=self.settings.PLAYWRIGHT_HEADLESS,
            )
            logger.info("Playwright browser started")
        except Exception as e:
            logger.error(f"Failed to start Playwright: {e}")
            raise BrowserError(f"Failed to start browser: {e}") from e

    async def stop(self) -> None:
        """Stop Playwright and browser."""
        try:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("Playwright browser stopped")
        except Exception as e:
            logger.error(f"Failed to stop Playwright: {e}")

    async def initialize_session(
        self,
        chat_id: int,
        email: str,
    ) -> tuple[str, str]:
        """
        Initialize Claude session: open login page, fill email, request login link.

        Args:
            chat_id: Telegram chat_id for isolating session
            email: Email address for Claude account

        Returns:
            Tuple of (session_path, status_message)

        Raises:
            BrowserError: If browser operation fails
        """
        session_path = self.settings.SESSION_DIR / str(chat_id)
        session_path.mkdir(parents=True, exist_ok=True, mode=0o700)

        context: BrowserContext | None = None
        page: Page | None = None

        try:
            # Create isolated browser context
            if self.browser is None:
                raise BrowserError("Browser not initialized. Call start() first.")
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
            logger.info(f"Opened login page for chat {chat_id}")

            # Fill email field
            email_input = page.locator('input[type="email"]')
            await email_input.fill(email)
            logger.info(f"Filled email for chat {chat_id}")

            # Click "Continue with email" button
            continue_button = page.locator('button:has-text("Continue with email")')
            await continue_button.click()

            # Wait for "Check your email" message
            await page.wait_for_selector(
                'text="Check your email"',
                timeout=self.settings.PLAYWRIGHT_TIMEOUT,
            )
            logger.info(f"Email sent confirmation for chat {chat_id}")

            # Save session state
            await context.storage_state(path=str(session_path / "state.json"))

            return (
                str(session_path),
                "📧 Email sent! Please send me the authorization link from your inbox.",
            )

        except PlaywrightTimeoutError as e:
            logger.error(f"Timeout during session init for chat {chat_id}: {e}")
            # Save error screenshot
            if page:
                screenshot_path = self.settings.ERROR_DIR / f"init_{chat_id}.png"
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(screenshot_path))
            raise BrowserError(
                "❌ Operation timed out. The page took too long to respond."
            ) from e
        except Exception as e:
            logger.error(f"Failed to initialize session for chat {chat_id}: {e}")
            raise BrowserError(f"❌ Failed to initialize session: {str(e)}") from e
        finally:
            if context:
                await context.close()

    async def process_login_link(
        self,
        chat_id: int,
        login_url: str,
    ) -> str:
        """
        Process Claude login link to complete authentication.

        Args:
            chat_id: Telegram chat_id
            login_url: Login URL from email

        Returns:
            Success message

        Raises:
            SessionError: If session doesn't exist
            BrowserError: If browser operation fails
        """
        session_path = self.settings.SESSION_DIR / str(chat_id)
        if not session_path.exists():
            raise SessionError("❌ No session found. Please run /init_session first.")

        context: BrowserContext | None = None
        page: Page | None = None

        try:
            # Load existing session
            if self.browser is None:
                raise BrowserError("Browser not initialized. Call start() first.")
            state_file = session_path / "state.json"
            context = await self.browser.new_context(
                storage_state=str(state_file) if state_file.exists() else None,
            )

            page = await context.new_page()

            # Open login link
            await page.goto(login_url, timeout=self.settings.PLAYWRIGHT_TIMEOUT)

            # Wait for successful authentication
            # Check for user profile element or dashboard
            await page.wait_for_selector(
                'button[aria-label="User menu"], [data-testid="user-menu"]',
                timeout=self.settings.PLAYWRIGHT_TIMEOUT,
                state="visible",
            )
            logger.info(f"Authentication successful for chat {chat_id}")

            # Save authenticated session
            await context.storage_state(path=str(session_path / "state.json"))

            return "✅ Session initialized successfully! You can now use /get_code."

        except PlaywrightTimeoutError as e:
            logger.error(f"Timeout during login for chat {chat_id}: {e}")
            if page:
                screenshot_path = self.settings.ERROR_DIR / f"login_{chat_id}.png"
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(screenshot_path))
            raise BrowserError(
                "❌ Login link is invalid or expired. Please run /init_session again."
            ) from e
        except Exception as e:
            logger.error(f"Failed to process login link for chat {chat_id}: {e}")
            raise BrowserError(f"❌ Failed to process login link: {str(e)}") from e
        finally:
            if context:
                await context.close()

    async def extract_authorization_code(
        self,
        chat_id: int,
        auth_url: str,
    ) -> str:
        """
        Extract authorization code from Claude authorization page.

        Args:
            chat_id: Telegram chat_id
            auth_url: Authorization URL from Claude Code

        Returns:
            Authorization code

        Raises:
            SessionError: If session doesn't exist or is invalid
            BrowserError: If code extraction fails
        """
        session_path = self.settings.SESSION_DIR / str(chat_id)
        state_file = session_path / "state.json"

        if not state_file.exists():
            raise SessionError(
                "❌ No active session found. Run /init_session <email> first."
            )

        context: BrowserContext | None = None
        page: Page | None = None

        try:
            # Load authenticated session
            if self.browser is None:
                raise BrowserError("Browser not initialized. Call start() first.")
            context = await self.browser.new_context(
                storage_state=str(state_file),
            )

            page = await context.new_page()

            # Navigate to authorization URL
            await page.goto(auth_url, timeout=self.settings.PLAYWRIGHT_TIMEOUT)

            # Wait for authorization code element
            # Try multiple possible selectors
            code_element = None
            selectors = [
                "code",  # <code> tag
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
                    logger.info(f"Extracted code for chat {chat_id}")
                    return code_text.strip()
                else:
                    raise BrowserError("Could not find authorization code on page")

            # Extract code text
            code = await code_element.text_content()
            if not code:
                code = await code_element.get_attribute("value")

            if not code:
                raise BrowserError("Authorization code element is empty")

            logger.info(f"Extracted code for chat {chat_id}")
            return code.strip()

        except PlaywrightTimeoutError as e:
            logger.error(f"Timeout extracting code for chat {chat_id}: {e}")
            if page:
                screenshot_path = self.settings.ERROR_DIR / f"extract_{chat_id}.png"
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(screenshot_path))
            raise BrowserError(
                "❌ Operation timed out. Could not extract authorization code."
            ) from e
        except SessionError:
            raise
        except Exception as e:
            logger.error(f"Failed to extract code for chat {chat_id}: {e}")

            # Check if session is invalid (401/403)
            if "401" in str(e) or "403" in str(e) or "unauthorized" in str(e).lower():
                # Clean up invalid session
                if state_file.exists():
                    state_file.unlink()
                raise SessionError(
                    "❌ Session expired or invalid. Please run /init_session <email> again."
                ) from e

            raise BrowserError(
                f"❌ Could not extract authorization code: {str(e)}"
            ) from e
        finally:
            if context:
                await context.close()
