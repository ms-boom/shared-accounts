"""Filter to check if message is from a group."""

from aiogram.filters import Filter
from aiogram.types import Message


class IsGroup(Filter):
    """
    Filter that checks if message is from a group.

    Usage:
        @router.message(Command("group_only"), IsGroup())
        async def group_handler(message: Message):
            # This handler only runs in groups
            pass
    """

    async def __call__(self, message: Message) -> bool:
        """
        Check if message is from a group.

        Args:
            message: Incoming message

        Returns:
            True if group or supergroup, False otherwise
        """
        return message.chat.type in ["group", "supergroup"]
