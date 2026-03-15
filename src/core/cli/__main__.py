"""CLI entry point for Claude Authorization Bot."""

import logging

import click

from core.cli.commands.account import account
from core.cli.commands.health import health
from core.config import get_settings
from core.logging_config import setup_logging


@click.group()
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    help="Set logging level",
)
@click.pass_context
def cli(ctx: click.Context, log_level: str | None) -> None:
    """
    Claude Authorization Bot CLI.

    Manage Claude sessions and authorization codes from command line.
    """
    # Ensure context object exists
    ctx.ensure_object(dict)

    # Load settings
    settings = get_settings()
    ctx.obj["settings"] = settings

    # Configure logging
    if log_level:
        settings.LOG_LEVEL = log_level
    setup_logging(settings)

    logger = logging.getLogger(__name__)
    logger.debug(f"CLI started with settings: {settings.model_dump()}")


# Register command groups and commands
cli.add_command(account)
cli.add_command(health)


if __name__ == "__main__":
    cli(obj={})
