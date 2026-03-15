"""Account management commands for CLI."""

import asyncio
import json
import logging
from pathlib import Path

import click

from core.config import Settings
from core.db.database import Database
from core.db.repositories.chat_session_repository import ChatSessionRepository
from core.exceptions import BrowserError, SessionError
from core.services.validation_service import ValidationService
from core.worker.playwright_service import PlaywrightService

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
        python -m core.cli account init-session /data/sessions/my-session user@example.com
    """
    settings: Settings = ctx.obj["settings"]
    session_dir = Path(session_path)

    # Validate email
    if not ValidationService.validate_email(email):
        click.echo(
            "❌ Invalid email format. Please provide a valid email address.", err=True
        )
        raise click.Abort()

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

            # Initialize session using SessionManagementService
            if playwright_service._session_service is None:
                raise BrowserError("Browser not initialized")

            message = await playwright_service._session_service.initialize_session(
                session_dir, email
            )

            click.echo(f"✅ {message}")
            click.echo(
                f"\nNext steps:\n"
                "1. Check your email for the login link from Claude\n"
                f"2. Run: python -m core.cli account process-login {session_dir} <login_url>"
            )

        except BrowserError as e:
            click.echo(f"❌ Browser error: {e}", err=True)
            raise click.Abort() from e
        except Exception as e:
            logger.error(f"Failed to initialize session: {e}", exc_info=True)
            click.echo(f"❌ Failed to initialize session: {e}", err=True)
            raise click.Abort() from e
        finally:
            await playwright_service.stop()

    asyncio.run(_run())


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
        python -m core.cli account process-login /data/sessions/my-session "https://claude.ai/login?token=..."
    """
    settings: Settings = ctx.obj["settings"]
    session_dir = Path(session_path)

    # Validate login URL
    if not ValidationService.is_claude_login_url(login_url):
        click.echo("❌ Invalid Claude login URL format.", err=True)
        raise click.Abort()

    click.echo("🔄 Processing login link")
    click.echo(f"📁 Session: {session_dir}")

    async def _run() -> None:
        playwright_service = PlaywrightService(settings)

        try:
            await playwright_service.start()

            # Use SessionManagementService
            if playwright_service._session_service is None:
                raise BrowserError("Browser not initialized")

            message = await playwright_service._session_service.process_login(
                session_dir, login_url
            )

            click.echo(f"✅ {message}")
            click.echo(
                f"\nYou can now use:\n"
                f"python -m core.cli account get-code {session_dir} <auth_url>"
            )

        except SessionError as e:
            click.echo(f"❌ Session error: {e}", err=True)
            raise click.Abort() from e
        except BrowserError as e:
            click.echo(f"❌ Browser error: {e}", err=True)
            raise click.Abort() from e
        except Exception as e:
            logger.error(f"Failed to process login link: {e}", exc_info=True)
            click.echo(f"❌ Failed to process login link: {e}", err=True)
            raise click.Abort() from e
        finally:
            await playwright_service.stop()

    asyncio.run(_run())


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
        python -m core.cli account get-code /data/sessions/my-session "https://claude.ai/auth/authorize?..."
    """
    settings: Settings = ctx.obj["settings"]
    session_dir = Path(session_path)

    # Validate authorization URL
    if not ValidationService.is_claude_auth_url(auth_url):
        click.echo("❌ Invalid Claude authorization URL format.", err=True)
        raise click.Abort()

    click.echo("🔄 Extracting authorization code")
    click.echo(f"📁 Session: {session_dir}")

    async def _run() -> None:
        playwright_service = PlaywrightService(settings)

        try:
            await playwright_service.start()

            # Use SessionManagementService
            if playwright_service._session_service is None:
                raise BrowserError("Browser not initialized")

            code = await playwright_service._session_service.extract_code(
                session_dir, auth_url
            )

            click.echo("\n✅ Authorization code:\n")
            click.echo(f"    {code}\n")
            click.echo("Copy this code and paste it into Claude Code CLI.")

        except SessionError as e:
            click.echo(f"❌ Session error: {e}", err=True)
            raise click.Abort() from e
        except BrowserError as e:
            click.echo(f"❌ Browser error: {e}", err=True)
            raise click.Abort() from e
        except Exception as e:
            logger.error(f"Failed to extract code: {e}", exc_info=True)
            click.echo(f"❌ Failed to extract code: {e}", err=True)
            raise click.Abort() from e
        finally:
            await playwright_service.stop()

    asyncio.run(_run())


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
        python -m core.cli account list-chats
        python -m core.cli account list-chats --format json
    """
    settings: Settings = ctx.obj["settings"]

    async def _run() -> None:
        database = Database(settings)

        try:
            await database.startup()

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
                        "\nUse session paths with other commands:\n"
                        "  python -m core.cli account get-code <session_path> <auth_url>"
                    )

        except Exception as e:
            logger.error(f"Failed to list chat sessions: {e}", exc_info=True)
            click.echo(f"❌ Failed to list chat sessions: {e}", err=True)
            raise click.Abort() from e
        finally:
            await database.shutdown()

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
        python -m core.cli account delete-session /data/sessions/my-session
        python -m core.cli account delete-session /data/sessions/my-session --force
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
        raise click.Abort() from e
