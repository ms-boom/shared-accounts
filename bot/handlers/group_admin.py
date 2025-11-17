"""Handlers for group administration commands."""

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.filters.is_group_admin import IsGroupAdmin

logger = logging.getLogger(__name__)

router = Router(name="group_admin")


@router.message(Command("admin_demo"), IsGroupAdmin())
async def admin_demo_handler(message: Message) -> None:
    """
    Demo handler for admin-only commands.

    This is an example of how to create commands that only group administrators can use.
    Replace this with your actual admin commands.

    Args:
        message: Incoming message
    """
    await message.reply(
        "✅ Команда выполнена администратором!\n\n"
        "Это пример команды, доступной только администраторам группы.\n"
        "Замените этот handler на свою логику."
    )
    logger.info(
        f"Admin command executed by user {message.from_user.id if message.from_user else 'unknown'} "
        f"in group {message.chat.id}"
    )
