"""Integration tests for TaskRepository with PostgreSQL.

These tests should be run against real PostgreSQL database.
"""

import pytest


@pytest.mark.integration
@pytest.mark.skip(reason="Integration tests require PostgreSQL database")
def test_placeholder() -> None:
    """Placeholder test for integration tests."""
    pass
