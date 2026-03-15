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
        "Я бот для авторизации Claude Code.\n"
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
    is_group = message.chat.type in ["group", "supergroup"]

    help_text = "📚 <b>Доступные команды:</b>\n\n"

    help_text += "🔹 /start - Начать работу с ботом\n"
    help_text += "🔹 /help - Показать это сообщение\n"
    help_text += "🔹 /health - Проверить состояние системы\n"

    if is_group:
        help_text += "\n<b>Авторизация Claude Code:</b>\n"
        help_text += "🔹 /init_session &lt;email&gt; - Инициализировать сессию (только админы)\n"
        help_text += "🔹 /get_code &lt;url&gt; - Получить код авторизации\n"

    await message.reply(help_text, parse_mode="HTML")
    logger.info(
        f"Help requested by user {message.from_user.id if message.from_user else 'unknown'}"
    )
