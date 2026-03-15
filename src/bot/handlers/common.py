"""Common handlers for basic bot commands."""

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

logger = logging.getLogger(__name__)

router = Router(name="common")


@router.message(Command("start"))
async def start_handler(message: Message) -> None:
    """
    Handle /start command.

    Available to all users in any chat type.

    Args:
        message: Incoming message
    """
    user_name = message.from_user.first_name if message.from_user else "User"
    await message.reply(
        f"👋 Привет, {user_name}!\n\n"
        "Я бот-шаблон для работы с группами Telegram.\n"
        "Используй /help чтобы узнать доступные команды."
    )
    logger.info(
        f"User {message.from_user.id if message.from_user else 'unknown'} started the bot"
    )


@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    """
    Handle /help command.

    Shows available commands based on chat type.

    Args:
        message: Incoming message
    """
    is_private = message.chat.type == "private"
    is_group = message.chat.type in ["group", "supergroup"]

    help_text = "📚 <b>Доступные команды:</b>\n\n"

    # Common commands
    help_text += "🔹 /start - Начать работу с ботом\n"
    help_text += "🔹 /help - Показать это сообщение\n"

    if is_private:
        help_text += "\n<b>В приватном чате:</b>\n"
        help_text += "🔹 /configure - Настроить группу (для администраторов)\n"

    if is_group:
        help_text += "\n<b>В группе:</b>\n"
        help_text += "🔹 Базовые команды доступны всем участникам\n"
        help_text += "🔹 Команды администрирования доступны только администраторам\n"

    help_text += "\n<i>Это шаблон бота. Добавьте свои команды и функциональность!</i>"

    await message.reply(help_text, parse_mode="HTML")
    logger.info(
        f"Help requested by user {message.from_user.id if message.from_user else 'unknown'}"
    )
