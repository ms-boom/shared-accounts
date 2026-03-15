"""Logging configuration for the bot application."""

import logging
import sys
from pathlib import Path

from core.config import Settings


def setup_logging(settings: Settings) -> None:
    """
    Configure application logging.

    Args:
        settings: Application settings containing log level and format
    """
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # Configure root logger
    logging.basicConfig(
        level=settings.LOG_LEVEL,
        format=settings.LOG_FORMAT,
        handlers=[
            # Console handler - output to stdout
            logging.StreamHandler(sys.stdout),
            # File handler - write to file with rotation
            logging.FileHandler(
                logs_dir / "bot.log",
                encoding="utf-8",
            ),
        ],
    )

    # Set specific log levels for noisy libraries
    logging.getLogger("aiogram").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)

    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured with level: {settings.LOG_LEVEL}")
    if settings.DEBUG:
        logger.warning("DEBUG mode is enabled - DO NOT use in production!")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
