"""Tests for DI container wiring of the fingerprint core services."""

import pytest

from bot.container import create_container
from core.config import Settings
from core.services.fingerprint_management_service import FingerprintManagementService
from core.services.fingerprint_resolution_service import FingerprintResolutionService


@pytest.mark.unit
def test__container__resolves_fingerprint_resolution_service_as_singleton(
    test_settings: Settings,
) -> None:
    container = create_container(test_settings)

    first = container.resolve(FingerprintResolutionService)
    second = container.resolve(FingerprintResolutionService)

    assert isinstance(first, FingerprintResolutionService)
    assert first is second


@pytest.mark.unit
def test__container__resolves_fingerprint_management_service_as_singleton(
    test_settings: Settings,
) -> None:
    container = create_container(test_settings)

    first = container.resolve(FingerprintManagementService)
    second = container.resolve(FingerprintManagementService)

    assert isinstance(first, FingerprintManagementService)
    assert first is second


@pytest.mark.unit
def test__container__resolution_service_default_matches_settings(
    test_settings: Settings,
) -> None:
    container = create_container(test_settings)

    resolution_service = container.resolve(FingerprintResolutionService)
    default = resolution_service.default()

    assert default.user_agent == test_settings.DEFAULT_USER_AGENT
    assert default.cpu_cores == test_settings.DEFAULT_CPU_CORES
