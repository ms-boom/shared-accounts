"""FSM states for group settings configuration."""

from aiogram.fsm.state import State, StatesGroup


class GroupSettingsStates(StatesGroup):
    """
    States for group settings configuration in private chat.

    Flow:
        1. User starts configuration (/configure)
        2. Bot shows list of groups (selecting_group state)
        3. User selects a group
        4. Bot enters configuring state
        5. User can change settings for selected group
        6. User exits configuration
    """

    selecting_group = State()  # User is selecting which group to configure
    configuring = State()  # User is configuring selected group
