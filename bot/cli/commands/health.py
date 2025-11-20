"""Health check command for CLI."""

import asyncio
import json
import logging

import click
import sqlalchemy as sa

from bot.core.config import Settings
from bot.db.database import Database
from bot.db.repositories.chat_session_repository import ChatSessionRepository
from bot.db.repositories.task_repository import TaskRepository

logger = logging.getLogger(__name__)


@click.command()
@click.option(
    "--format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
@click.pass_context
def health(ctx: click.Context, format: str) -> None:
    """
    Check system health status.

    Shows database connection, active sessions, and pending tasks.
    """
    settings: Settings = ctx.obj["settings"]

    async def _run() -> None:
        database = Database(settings)

        try:
            await database.startup()

            async with database.session_maker() as session, session.begin():
                # Check database connection
                db_status = "disconnected"
                db_error = None
                try:
                    result = await session.execute(sa.text("SELECT 1"))
                    db_status = "connected" if result else "error"
                except Exception as e:
                    db_status = "disconnected"
                    db_error = str(e)
                    logger.error(f"Database health check failed: {e}")

                # Get active sessions count
                sessions_count = 0
                sessions_error = None
                try:
                    session_repo = ChatSessionRepository(session)
                    sessions = await session_repo.get_all_active()
                    sessions_count = len(sessions)
                except Exception as e:
                    sessions_error = str(e)
                    logger.error(f"Failed to get sessions count: {e}")

                # Get pending tasks count
                pending_count = 0
                tasks_error = None
                try:
                    task_repo = TaskRepository(session)
                    pending_count = await task_repo.get_pending_count()
                except Exception as e:
                    tasks_error = str(e)
                    logger.error(f"Failed to get pending tasks count: {e}")

            if format == "json":
                health_data = {
                    "status": "healthy" if db_status == "connected" else "unhealthy",
                    "database": {
                        "status": db_status,
                        "error": db_error,
                    },
                    "sessions": {
                        "active_count": sessions_count,
                        "error": sessions_error,
                    },
                    "tasks": {
                        "pending_count": pending_count,
                        "error": tasks_error,
                    },
                }
                click.echo(json.dumps(health_data, indent=2))
            else:
                # Text format
                click.echo("\n✅ System Health Status\n")
                click.echo("=" * 50)

                # Database status
                db_icon = "✅" if db_status == "connected" else "❌"
                click.echo(f"\n{db_icon} Database: {db_status.upper()}")
                if db_error:
                    click.echo(f"   Error: {db_error}")

                # Sessions
                sessions_icon = "✅" if sessions_error is None else "❌"
                click.echo(f"{sessions_icon} Active sessions: {sessions_count}")
                if sessions_error:
                    click.echo(f"   Error: {sessions_error}")

                # Tasks
                tasks_icon = "✅" if tasks_error is None else "❌"
                click.echo(f"{tasks_icon} Pending tasks: {pending_count}")
                if tasks_error:
                    click.echo(f"   Error: {tasks_error}")

                click.echo("\n" + "=" * 50 + "\n")

                # Overall status
                overall_healthy = (
                    db_status == "connected"
                    and sessions_error is None
                    and tasks_error is None
                )
                if overall_healthy:
                    click.echo("✅ All systems operational")
                else:
                    click.echo("⚠️  Some systems are experiencing issues")

        except Exception as e:
            logger.error(f"Health check failed: {e}", exc_info=True)
            click.echo(f"❌ Health check failed: {e}", err=True)
            raise click.Abort() from e
        finally:
            await database.shutdown()

    asyncio.run(_run())
