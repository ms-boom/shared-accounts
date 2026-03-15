"""Dependency Injection container using punq."""

import punq

from core.config import Settings
from core.db.database import Database


def create_container(settings: Settings) -> punq.Container:
    """
    Create and configure the DI container.

    Args:
        settings: Application settings

    Returns:
        Configured punq container with all dependencies
    """
    container = punq.Container()

    # Register settings as singleton
    container.register(Settings, instance=settings)

    # Register database as singleton
    container.register(Database, scope=punq.Scope.singleton)

    # Services will be registered here as we implement them
    # container.register(GroupService, scope=punq.Scope.singleton)
    # container.register(PermissionService, scope=punq.Scope.singleton)
    # container.register(GroupContextService, scope=punq.Scope.singleton)

    return container
