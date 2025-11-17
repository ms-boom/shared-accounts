"""Handlers for group lifecycle events."""

import logging

from aiogram import Router
from aiogram.types import ChatMemberUpdated

from bot.services.group_service import GroupService

logger = logging.getLogger(__name__)

router = Router(name="group_events")


@router.my_chat_member()
async def on_bot_status_changed(
    event: ChatMemberUpdated,
    group_service: GroupService,
) -> None:
    """
    Handle bot status changes in chats.

    Triggered when:
    - Bot is added to a group
    - Bot is removed from a group
    - Bot permissions are changed

    Args:
        event: Chat member update event
        group_service: Service for group operations
    """
    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status

    # Bot was added to group
    if new_status in ["member", "administrator"] and old_status in ["left", "kicked"]:
        logger.info("Bot added to group %s (%s)", event.chat.id, event.chat.title)
        try:
            await group_service.register_group(event.chat)
            logger.info("Group %s registered successfully", event.chat.id)
        except Exception as e:
            logger.error("Failed to register group %s: %s", event.chat.id, e)

    # Bot was removed from group
    elif old_status in ["member", "administrator"] and new_status in ["left", "kicked"]:
        logger.info("Bot removed from group %s (%s)", event.chat.id, event.chat.title)
        # Note: We don't delete the group from database (soft delete pattern)
        # You might want to add a "is_active" field to track this

    # Bot permissions changed
    elif old_status != new_status:
        logger.info(
            f"Bot status changed in group {event.chat.id}: {old_status} -> {new_status}"
        )
