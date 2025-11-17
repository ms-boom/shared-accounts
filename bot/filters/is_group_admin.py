"""Filter to check if user is group administrator."""

from aiogram.filters import Filter
from aiogram.types import Message

from bot.services.permission_service import PermissionService


class IsGroupAdmin(Filter):
    """
    Filter that checks if user is administrator in the group.

    Usage:
        @router.message(Command("admin_command"), IsGroupAdmin())
        async def admin_handler(message: Message):
            # This handler only runs if user is admin
            pass
    """

    async def __call__(
        self,
        message: Message,
        permission_service: PermissionService,
    ) -> bool:
        """
        Check if message sender is group administrator.

        Args:
            message: Incoming message
            permission_service: Permission service (injected via DI)

        Returns:
            True if user is admin, False otherwise
        """
        if not message.chat or not message.from_user:
            return False

        # Only check in groups
        if message.chat.type not in ["group", "supergroup"]:
            return False

        bot = message.bot
        return await permission_service.is_group_admin(
            bot=bot,
            user_id=message.from_user.id,
            chat_id=message.chat.id,
        )
