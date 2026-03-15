"""Filter to check if message is from private chat."""

from aiogram.filters import Filter
from aiogram.types import Message


class IsPrivateChat(Filter):
    """
    Filter that checks if message is from private chat.

    Usage:
        @router.message(Command("settings"), IsPrivateChat())
        async def settings_handler(message: Message):
            # This handler only runs in private chats
            pass
    """

    async def __call__(self, message: Message) -> bool:
        """
        Check if message is from private chat.

        Args:
            message: Incoming message

        Returns:
            True if private chat, False otherwise
        """
        # aiogram types are not fully typed, explicit bool conversion
        is_private: bool = message.chat.type == "private"
        return is_private
