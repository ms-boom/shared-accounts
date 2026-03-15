"""Playwright automation service for Claude.ai interactions."""

import logging
from pathlib import Path

from playwright.async_api import (
    Browser,
    Playwright,
    async_playwright,
)

from core.config import Settings
from core.exceptions import BrowserError
from core.services.session_management_service import SessionManagementService

logger = logging.getLogger(__name__)


class PlaywrightService:
    """
    Service for automating Claude.ai interactions with Playwright.

    Manages browser sessions, handles authentication, and extracts authorization codes.
    This service is a wrapper around SessionManagementService that provides
    chat_id/thread_id based session management for Telegram bot integration.
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
        self._session_service: SessionManagementService | None = None

    async def start(self) -> None:
        """Start Playwright and browser."""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=self.settings.PLAYWRIGHT_HEADLESS,
            )
            self._session_service = SessionManagementService(
                self.settings, self.browser
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

    def _get_session_path(self, chat_id: int, thread_id: int = 0) -> Path:
        """
        Build session path for chat_id and thread_id.

        Args:
            chat_id: Telegram chat_id
            thread_id: Telegram thread_id (0 for main chat, >0 for topics)

        Returns:
            Path to session directory
        """
        if thread_id == 0:
            return self.settings.SESSION_DIR / str(chat_id)
        return self.settings.SESSION_DIR / str(chat_id) / str(thread_id)

    async def initialize_session(
        self,
        chat_id: int,
        email: str,
        thread_id: int = 0,
    ) -> tuple[str, str]:
        """
        Initialize Claude session: open login page, fill email, request login link.

        Args:
            chat_id: Telegram chat_id for isolating session
            email: Email address for Claude account
            thread_id: Telegram thread_id (0 for main chat, >0 for topics)

        Returns:
            Tuple of (session_path, status_message)

        Raises:
            BrowserError: If browser operation fails
        """
        if self._session_service is None:
            raise BrowserError("Browser not initialized. Call start() first.")

        session_path = self._get_session_path(chat_id, thread_id)
        message = await self._session_service.initialize_session(session_path, email)
        return (str(session_path), message)

    async def process_login_link(
        self,
        chat_id: int,
        login_url: str,
        thread_id: int = 0,
    ) -> str:
        """
        Process Claude login link to complete authentication.

        Args:
            chat_id: Telegram chat_id
            login_url: Login URL from email
            thread_id: Telegram thread_id (0 for main chat, >0 for topics)

        Returns:
            Success message

        Raises:
            SessionError: If session doesn't exist
            BrowserError: If browser operation fails
        """
        if self._session_service is None:
            raise BrowserError("Browser not initialized. Call start() first.")

        session_path = self._get_session_path(chat_id, thread_id)
        return await self._session_service.process_login(session_path, login_url)

    async def extract_authorization_code(
        self,
        chat_id: int,
        auth_url: str,
        thread_id: int = 0,
    ) -> str:
        """
        Extract authorization code from Claude authorization page.

        Args:
            chat_id: Telegram chat_id
            auth_url: Authorization URL from Claude Code
            thread_id: Telegram thread_id (0 for main chat, >0 for topics)

        Returns:
            Authorization code

        Raises:
            SessionError: If session doesn't exist or is invalid
            BrowserError: If code extraction fails
        """
        if self._session_service is None:
            raise BrowserError("Browser not initialized. Call start() first.")

        session_path = self._get_session_path(chat_id, thread_id)
        return await self._session_service.extract_code(session_path, auth_url)
