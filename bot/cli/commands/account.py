"""Account management commands for CLI."""

import asyncio
import json
import logging
from pathlib import Path

import click

from bot.core.config import Settings
from bot.core.exceptions import BrowserError, SessionError
from bot.db.database import Database
from bot.db.repositories.chat_session_repository import ChatSessionRepository
from bot.worker.playwright_service import PlaywrightService

logger = logging.getLogger(__name__)


@click.group()
def account() -> None:
    """Manage Claude account sessions."""
    pass


@account.command("init-session")
@click.argument("session_path", type=click.Path())
@click.argument("email")
@click.pass_context
def init_session(ctx: click.Context, session_path: str, email: str) -> None:
    """
    Initialize Claude session at specified path.

    Args:
        session_path: Path where Playwright session will be stored
        email: Email address for Claude account

    Example:
        python -m bot.cli account init-session /data/sessions/my-session user@example.com
    """
    settings: Settings = ctx.obj["settings"]
    session_dir = Path(session_path)

    click.echo(f"🔄 Initializing session for {email}")
    click.echo(f"📁 Session path: {session_dir}")

    async def _run() -> None:
        playwright_service = PlaywrightService(settings)

        try:
            # Start Playwright
            await playwright_service.start()

            # Check if session already exists
            if session_dir.exists():
                click.echo(f"⚠️  Session directory already exists: {session_dir}")
                if not click.confirm("Overwrite existing session?"):
                    click.echo("❌ Operation cancelled")
                    return

            # Create session directory
            session_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

            # Initialize session using path directly
            message = await _initialize_session_at_path(
                playwright_service, session_dir, email
            )

            click.echo(f"✅ {message}")
            click.echo(
                f"\nNext steps:\n"
                "1. Check your email for the login link from Claude\n"
                f"2. Run: python -m bot.cli account process-login {session_dir} <login_url>"
            )

        except BrowserError as e:
            click.echo(f"❌ Browser error: {e}", err=True)
            raise click.Abort()
        except Exception as e:
            logger.error(f"Failed to initialize session: {e}", exc_info=True)
            click.echo(f"❌ Failed to initialize session: {e}", err=True)
            raise click.Abort()
        finally:
            await playwright_service.stop()

    asyncio.run(_run())


async def _initialize_session_at_path(
    playwright_service: PlaywrightService, session_path: Path, email: str
) -> str:
    """
    Initialize Claude session at specific path.

    Args:
        playwright_service: Playwright service instance
        session_path: Path to store session
        email: Email address for Claude account

    Returns:
        Success message
    """
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError

    context = None
    page = None

    try:
        if playwright_service.browser is None:
            raise BrowserError("Browser not initialized. Call start() first.")

        context = await playwright_service.browser.new_context(
            storage_state=None,
            viewport={"width": 1280, "height": 720},
        )

        page = await context.new_page()

        # Navigate to Claude login page
        await page.goto(
            "https://claude.ai/login",
            timeout=playwright_service.settings.PLAYWRIGHT_TIMEOUT,
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
            timeout=playwright_service.settings.PLAYWRIGHT_TIMEOUT,
        )
        logger.info(f"Email sent confirmation for session {session_path}")

        # Save session state
        await context.storage_state(path=str(session_path / "state.json"))

        return "📧 Email sent! Please check your inbox for the authorization link."

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


@account.command("process-login")
@click.argument("session_path", type=click.Path(exists=True))
@click.argument("login_url")
@click.pass_context
def process_login(ctx: click.Context, session_path: str, login_url: str) -> None:
    """
    Process Claude login link to complete authentication.

    Args:
        session_path: Path to Playwright session directory
        login_url: Login URL from Claude email

    Example:
        python -m bot.cli account process-login /data/sessions/my-session "https://claude.ai/login?token=..."
    """
    settings: Settings = ctx.obj["settings"]
    session_dir = Path(session_path)

    click.echo(f"🔄 Processing login link")
    click.echo(f"📁 Session: {session_dir}")

    async def _run() -> None:
        playwright_service = PlaywrightService(settings)

        try:
            await playwright_service.start()

            message = await _process_login_at_path(
                playwright_service, session_dir, login_url
            )

            click.echo(f"✅ {message}")
            click.echo(
                f"\nYou can now use:\n"
                f"python -m bot.cli account get-code {session_dir} <auth_url>"
            )

        except SessionError as e:
            click.echo(f"❌ Session error: {e}", err=True)
            raise click.Abort()
        except BrowserError as e:
            click.echo(f"❌ Browser error: {e}", err=True)
            raise click.Abort()
        except Exception as e:
            logger.error(f"Failed to process login link: {e}", exc_info=True)
            click.echo(f"❌ Failed to process login link: {e}", err=True)
            raise click.Abort()
        finally:
            await playwright_service.stop()

    asyncio.run(_run())


async def _process_login_at_path(
    playwright_service: PlaywrightService, session_path: Path, login_url: str
) -> str:
    """
    Process Claude login link at specific path.

    Args:
        playwright_service: Playwright service instance
        session_path: Path to session directory
        login_url: Login URL from email

    Returns:
        Success message
    """
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError

    state_file = session_path / "state.json"
    if not state_file.exists():
        raise SessionError(
            f"❌ No session found at {session_path}. Run init-session first."
        )

    context = None
    page = None

    try:
        if playwright_service.browser is None:
            raise BrowserError("Browser not initialized. Call start() first.")

        context = await playwright_service.browser.new_context(
            storage_state=str(state_file),
        )

        page = await context.new_page()

        # Open login link
        await page.goto(login_url, timeout=playwright_service.settings.PLAYWRIGHT_TIMEOUT)

        # Wait for successful authentication
        await page.wait_for_selector(
            'button[aria-label="User menu"], [data-testid="user-menu"]',
            timeout=playwright_service.settings.PLAYWRIGHT_TIMEOUT,
            state="visible",
        )
        logger.info(f"Authentication successful for session {session_path}")

        # Save authenticated session
        await context.storage_state(path=str(state_file))

        return "Session authenticated successfully!"

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


@account.command("get-code")
@click.argument("session_path", type=click.Path(exists=True))
@click.argument("auth_url")
@click.pass_context
def get_code(ctx: click.Context, session_path: str, auth_url: str) -> None:
    """
    Extract authorization code from Claude authorization URL.

    Args:
        session_path: Path to Playwright session directory
        auth_url: Authorization URL from Claude Code

    Example:
        python -m bot.cli account get-code /data/sessions/my-session "https://claude.ai/auth/authorize?..."
    """
    settings: Settings = ctx.obj["settings"]
    session_dir = Path(session_path)

    click.echo(f"🔄 Extracting authorization code")
    click.echo(f"📁 Session: {session_dir}")

    async def _run() -> None:
        playwright_service = PlaywrightService(settings)

        try:
            await playwright_service.start()

            code = await _extract_code_at_path(
                playwright_service, session_dir, auth_url
            )

            click.echo(f"\n✅ Authorization code:\n")
            click.echo(f"    {code}\n")
            click.echo("Copy this code and paste it into Claude Code CLI.")

        except SessionError as e:
            click.echo(f"❌ Session error: {e}", err=True)
            raise click.Abort()
        except BrowserError as e:
            click.echo(f"❌ Browser error: {e}", err=True)
            raise click.Abort()
        except Exception as e:
            logger.error(f"Failed to extract code: {e}", exc_info=True)
            click.echo(f"❌ Failed to extract code: {e}", err=True)
            raise click.Abort()
        finally:
            await playwright_service.stop()

    asyncio.run(_run())


async def _extract_code_at_path(
    playwright_service: PlaywrightService, session_path: Path, auth_url: str
) -> str:
    """
    Extract authorization code at specific path.

    Args:
        playwright_service: Playwright service instance
        session_path: Path to session directory
        auth_url: Authorization URL from Claude Code

    Returns:
        Authorization code
    """
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError

    state_file = session_path / "state.json"
    if not state_file.exists():
        raise SessionError(
            f"❌ No active session found at {session_path}. Run init-session first."
        )

    context = None
    page = None

    try:
        if playwright_service.browser is None:
            raise BrowserError("Browser not initialized. Call start() first.")

        context = await playwright_service.browser.new_context(
            storage_state=str(state_file),
        )

        page = await context.new_page()

        # Navigate to authorization URL
        await page.goto(auth_url, timeout=playwright_service.settings.PLAYWRIGHT_TIMEOUT)

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
            code_text = await page.locator("text=/^[A-Z0-9]{8,}$/").first.text_content()

            if code_text:
                logger.info(f"Extracted code for session {session_path}")
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


@account.command("list-chats")
@click.option(
    "--format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
@click.pass_context
def list_chats(ctx: click.Context, format: str) -> None:
    """
    List all chat sessions from database with their session paths.

    Shows chat_id, thread_id, email, and session path for each chat.

    Example:
        python -m bot.cli account list-chats
        python -m bot.cli account list-chats --format json
    """
    settings: Settings = ctx.obj["settings"]

    async def _run() -> None:
        database = Database(settings.DATABASE_URL)

        try:
            await database.connect()

            async with database.session_maker() as session, session.begin():
                session_repo = ChatSessionRepository(session)
                sessions = await session_repo.get_all_active()

                if not sessions:
                    click.echo("No chat sessions found in database.")
                    return

                if format == "json":
                    # Convert datetime to string for JSON serialization
                    sessions_json = []
                    for s in sessions:
                        s_copy = s.copy()
                        s_copy["created_at"] = (
                            s_copy["created_at"].isoformat()
                            if s_copy.get("created_at")
                            else None
                        )
                        s_copy["last_used"] = (
                            s_copy["last_used"].isoformat()
                            if s_copy.get("last_used")
                            else None
                        )
                        sessions_json.append(s_copy)

                    click.echo(json.dumps(sessions_json, indent=2))
                else:
                    # Table format
                    click.echo(
                        f"\n{'Chat ID':<15} {'Thread':<10} {'Email':<30} {'Session Path'}"
                    )
                    click.echo("-" * 120)

                    for s in sessions:
                        click.echo(
                            f"{s['chat_id']:<15} {s['thread_id']:<10} "
                            f"{s['email']:<30} {s['session_path']}"
                        )

                    click.echo(f"\nTotal chats: {len(sessions)}")
                    click.echo(
                        f"\nUse session paths with other commands:\n"
                        f"  python -m bot.cli account get-code <session_path> <auth_url>"
                    )

        except Exception as e:
            logger.error(f"Failed to list chat sessions: {e}", exc_info=True)
            click.echo(f"❌ Failed to list chat sessions: {e}", err=True)
            raise click.Abort()
        finally:
            await database.disconnect()

    asyncio.run(_run())


@account.command("delete-session")
@click.argument("session_path", type=click.Path(exists=True))
@click.option("--force", is_flag=True, help="Skip confirmation")
@click.pass_context
def delete_session(ctx: click.Context, session_path: str, force: bool) -> None:
    """
    Delete Claude session directory.

    Args:
        session_path: Path to Playwright session directory
        force: Skip confirmation prompt

    Example:
        python -m bot.cli account delete-session /data/sessions/my-session
        python -m bot.cli account delete-session /data/sessions/my-session --force
    """
    session_dir = Path(session_path)

    if not force and not click.confirm(f"Delete session at {session_dir}?"):
        click.echo("❌ Operation cancelled")
        return

    try:
        import shutil

        if session_dir.exists():
            shutil.rmtree(session_dir)
            click.echo(f"✅ Deleted session: {session_dir}")
        else:
            click.echo(f"❌ Session directory not found: {session_dir}")

    except Exception as e:
        logger.error(f"Failed to delete session: {e}", exc_info=True)
        click.echo(f"❌ Failed to delete session: {e}", err=True)
        raise click.Abort()
