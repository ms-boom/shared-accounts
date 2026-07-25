"""Dependency Injection container using punq."""

import punq

from core.config import Settings
from core.db.database import Database
from core.services.fingerprint_management_service import FingerprintManagementService
from core.services.fingerprint_resolution_service import FingerprintResolutionService


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

    # Resolution builds its default profile once from Settings; management is
    # stateless (its methods take a session, supplied by the caller).
    container.register(FingerprintResolutionService, scope=punq.Scope.singleton)
    container.register(FingerprintManagementService, scope=punq.Scope.singleton)

    # Services will be registered here as we implement them
    # container.register(GroupService, scope=punq.Scope.singleton)
    # container.register(PermissionService, scope=punq.Scope.singleton)
    # container.register(GroupContextService, scope=punq.Scope.singleton)

    return container
