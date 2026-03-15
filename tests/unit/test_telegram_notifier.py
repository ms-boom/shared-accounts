"""Tests for TelegramNotifier adapter."""

import pytest

from bot.adapters.telegram_notifier import TelegramNotifier
from core.ports import TaskNotifier


@pytest.mark.unit
def test_telegram_notifier_satisfies_task_notifier_protocol() -> None:
    """TelegramNotifier must structurally satisfy TaskNotifier protocol.

    Because TaskNotifier is @runtime_checkable, isinstance() performs structural
    duck-typing check at runtime. If the protocol gains a new method and
    TelegramNotifier is not updated, this test will fail.
    """
    assert isinstance(TelegramNotifier.__new__(TelegramNotifier), TaskNotifier)
