"""Environment fixtures for testing.

This module provides session-scoped event loop fixture
that must be loaded first to ensure proper async test execution.
"""

import asyncio
from collections.abc import Generator

import pytest


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Session-scoped event loop for async tests and fixtures.

    This fixture overrides pytest-asyncio's default function-scoped event loop.
    Session scope ensures that session-scoped async fixtures (db_engine, db_connection)
    share the same event loop with function-scoped tests, preventing
    "got Future attached to a different loop" errors.

    Pattern from intern-contest-cabinet project for compatibility with asyncio_mode="auto".
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    asyncio.set_event_loop(None)
    loop.close()
