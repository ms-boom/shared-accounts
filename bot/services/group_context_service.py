"""Service for managing group context in FSM state."""

import logging

from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)


class GroupContextService:
    """
    Service for managing selected group in FSM state.

    Used in private chat scenarios where user selects a group
    and then performs operations on it.
    """

    async def set_selected_group(self, state: FSMContext, group_id: int) -> None:
        """
        Set selected group in FSM state.

        Args:
            state: FSM context
            group_id: Telegram chat_id to set as selected
        """
        await state.update_data(selected_group_id=group_id)
        logger.debug("Set selected group to %s", group_id)

    async def get_selected_group(self, state: FSMContext) -> int | None:
        """
        Get selected group from FSM state.

        Args:
            state: FSM context

        Returns:
            Selected group ID or None if not set
        """
        data = await state.get_data()
        group_id = data.get("selected_group_id")
        logger.debug("Retrieved selected group: %s", group_id)
        return group_id

    async def clear_selected_group(self, state: FSMContext) -> None:
        """
        Clear selected group from FSM state.

        Args:
            state: FSM context
        """
        data = await state.get_data()
        if "selected_group_id" in data:
            data.pop("selected_group_id")
            await state.set_data(data)
            logger.debug("Cleared selected group")
