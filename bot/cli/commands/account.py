"""Account management commands for CLI."""

import asyncio
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
@click.argument("chat_id", type=int)
@click.argument("thread_id", type=int, default=0)
@click.argument("email")
@click.pass_context
def init_session(ctx: click.Context, chat_id: int, thread_id: int, email: str) -> None:
    """
    Initialize Claude session for a chat.

    Args:
        chat_id: Telegram chat ID
        thread_id: Telegram thread ID (0 for main chat)
        email: Email address for Claude account
    """
    settings: Settings = ctx.obj["settings"]

    click.echo(f"🔄 Initializing session for {email} (chat={chat_id}, thread={thread_id})")

    async def _run() -> None:
        database = Database(settings.DATABASE_URL)
        playwright_service = PlaywrightService(settings)

        try:
            # Initialize database
            await database.connect()

            # Start Playwright
            await playwright_service.start()

            # Check for existing session
            async with database.session_maker() as session, session.begin():
                session_repo = ChatSessionRepository(session)
                existing = await session_repo.get_by_chat_id(chat_id, thread_id)

                if existing:
                    click.echo(
                        f"⚠️  Session already exists for this chat (email: {existing['email']})"
                    )
                    if not click.confirm(f"Replace with {email}?"):
                        click.echo("❌ Operation cancelled")
                        return

                # Initialize session
                session_path, message = await playwright_service.initialize_session(
                    chat_id=chat_id,
                    email=email,
                    thread_id=thread_id,
                )

                # Save session to database
                async with database.session_maker() as db_session, db_session.begin():
                    session_repo = ChatSessionRepository(db_session)
                    await session_repo.upsert(
                        chat_id=chat_id,
                        thread_id=thread_id,
                        email=email,
                        session_path=session_path,
                    )

                click.echo(f"✅ {message}")
                click.echo(
                    f"📁 Session saved to: {session_path}\n\n"
                    "Next steps:\n"
                    "1. Check your email for the login link from Claude\n"
                    "2. Send the link using: account process-login <chat_id> <thread_id> <login_url>"
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
            await database.disconnect()

    asyncio.run(_run())


@account.command("process-login")
@click.argument("chat_id", type=int)
@click.argument("thread_id", type=int, default=0)
@click.argument("login_url")
@click.pass_context
def process_login(
    ctx: click.Context, chat_id: int, thread_id: int, login_url: str
) -> None:
    """
    Process Claude login link to complete authentication.

    Args:
        chat_id: Telegram chat ID
        thread_id: Telegram thread ID (0 for main chat)
        login_url: Login URL from email
    """
    settings: Settings = ctx.obj["settings"]

    click.echo(f"🔄 Processing login link (chat={chat_id}, thread={thread_id})")

    async def _run() -> None:
        database = Database(settings.DATABASE_URL)
        playwright_service = PlaywrightService(settings)

        try:
            await database.connect()
            await playwright_service.start()

            # Process login link
            message = await playwright_service.process_login_link(
                chat_id=chat_id,
                login_url=login_url,
                thread_id=thread_id,
            )

            click.echo(f"✅ {message}")

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
            await database.disconnect()

    asyncio.run(_run())


@account.command("get-code")
@click.argument("chat_id", type=int)
@click.argument("thread_id", type=int, default=0)
@click.argument("auth_url")
@click.pass_context
def get_code(ctx: click.Context, chat_id: int, thread_id: int, auth_url: str) -> None:
    """
    Extract authorization code from Claude authorization URL.

    Args:
        chat_id: Telegram chat ID
        thread_id: Telegram thread ID (0 for main chat)
        auth_url: Authorization URL from Claude Code
    """
    settings: Settings = ctx.obj["settings"]

    click.echo(f"🔄 Extracting authorization code (chat={chat_id}, thread={thread_id})")

    async def _run() -> None:
        database = Database(settings.DATABASE_URL)
        playwright_service = PlaywrightService(settings)

        try:
            await database.connect()
            await playwright_service.start()

            # Check for existing session
            async with database.session_maker() as session, session.begin():
                session_repo = ChatSessionRepository(session)
                existing_session = await session_repo.get_by_chat_id(chat_id, thread_id)

                if not existing_session:
                    click.echo(
                        "❌ No active session found for this chat.\n\n"
                        "Run 'account init-session' first to initialize a session.",
                        err=True,
                    )
                    raise click.Abort()

            # Extract authorization code
            code = await playwright_service.extract_authorization_code(
                chat_id=chat_id,
                auth_url=auth_url,
                thread_id=thread_id,
            )

            # Update last_used timestamp
            async with database.session_maker() as db_session, db_session.begin():
                session_repo = ChatSessionRepository(db_session)
                await session_repo.update_last_used(chat_id, thread_id)

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
            await database.disconnect()

    asyncio.run(_run())


@account.command("list-sessions")
@click.option(
    "--chat-id",
    type=int,
    help="Filter by specific chat ID",
)
@click.option(
    "--format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
@click.pass_context
def list_sessions(ctx: click.Context, chat_id: int | None, format: str) -> None:
    """
    List all active Claude sessions.

    Args:
        chat_id: Optional chat ID to filter sessions
        format: Output format (table or json)
    """
    settings: Settings = ctx.obj["settings"]

    async def _run() -> None:
        database = Database(settings.DATABASE_URL)

        try:
            await database.connect()

            async with database.session_maker() as session, session.begin():
                session_repo = ChatSessionRepository(session)

                if chat_id:
                    # Get specific chat sessions (all threads)
                    all_sessions = await session_repo.get_all_active()
                    sessions = [s for s in all_sessions if s["chat_id"] == chat_id]
                else:
                    # Get all sessions
                    sessions = await session_repo.get_all_active()

                if not sessions:
                    click.echo("No active sessions found.")
                    return

                if format == "json":
                    import json

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
                        f"\n{'Chat ID':<15} {'Thread':<10} {'Email':<30} "
                        f"{'Created':<20} {'Last Used':<20}"
                    )
                    click.echo("-" * 100)

                    for s in sessions:
                        created = (
                            s["created_at"].strftime("%Y-%m-%d %H:%M")
                            if s.get("created_at")
                            else "N/A"
                        )
                        last_used = (
                            s["last_used"].strftime("%Y-%m-%d %H:%M")
                            if s.get("last_used")
                            else "Never"
                        )

                        click.echo(
                            f"{s['chat_id']:<15} {s['thread_id']:<10} "
                            f"{s['email']:<30} {created:<20} {last_used:<20}"
                        )

                    click.echo(f"\nTotal sessions: {len(sessions)}")

        except Exception as e:
            logger.error(f"Failed to list sessions: {e}", exc_info=True)
            click.echo(f"❌ Failed to list sessions: {e}", err=True)
            raise click.Abort()
        finally:
            await database.disconnect()

    asyncio.run(_run())


@account.command("delete-session")
@click.argument("chat_id", type=int)
@click.argument("thread_id", type=int, default=0)
@click.option("--force", is_flag=True, help="Skip confirmation")
@click.pass_context
def delete_session(
    ctx: click.Context, chat_id: int, thread_id: int, force: bool
) -> None:
    """
    Delete Claude session for a chat.

    Args:
        chat_id: Telegram chat ID
        thread_id: Telegram thread ID (0 for main chat)
        force: Skip confirmation prompt
    """
    settings: Settings = ctx.obj["settings"]

    if not force and not click.confirm(
        f"Delete session for chat {chat_id}/{thread_id}?"
    ):
        click.echo("❌ Operation cancelled")
        return

    async def _run() -> None:
        database = Database(settings.DATABASE_URL)

        try:
            await database.connect()

            async with database.session_maker() as session, session.begin():
                session_repo = ChatSessionRepository(session)

                # Check if session exists
                existing = await session_repo.get_by_chat_id(chat_id, thread_id)
                if not existing:
                    click.echo("❌ Session not found")
                    return

                # Delete from database
                await session_repo.delete(chat_id, thread_id)

                # Delete session files
                session_path = Path(existing["session_path"])
                if session_path.exists():
                    import shutil

                    shutil.rmtree(session_path)
                    click.echo(f"🗑️  Deleted session files: {session_path}")

                click.echo(f"✅ Session deleted for chat {chat_id}/{thread_id}")

        except Exception as e:
            logger.error(f"Failed to delete session: {e}", exc_info=True)
            click.echo(f"❌ Failed to delete session: {e}", err=True)
            raise click.Abort()
        finally:
            await database.disconnect()

    asyncio.run(_run())
