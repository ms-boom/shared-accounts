"""FSM states for the `/fingerprint` dialog."""

from aiogram.fsm.state import State, StatesGroup


class FingerprintStates(StatesGroup):
    """States for the browser-fingerprint set-own / edit-shared / copy dialog.

    Flow:
        1. `/fingerprint` shows the view card + menu (no state).
        2. [Set own] / [Edit for all N] enter the 5-step chain, starting at
           `setting_user_agent` and ending at `setting_locale`, whose
           completion performs the terminal write.
        3. [Copy from my session] enters `selecting_copy_source`, a single
           picker step.
    """

    setting_user_agent = State()
    setting_cpu_cores = State()
    setting_device_memory = State()
    setting_timezone = State()
    setting_locale = State()
    selecting_copy_source = State()
