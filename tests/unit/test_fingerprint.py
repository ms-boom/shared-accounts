"""Tests for the pure browser fingerprint domain module."""

import pytest

from core.fingerprint import (
    EffectiveFingerprint,
    FingerprintValues,
    build_label,
    build_navigator_init_script,
    validate_cpu_cores,
    validate_device_memory,
    validate_locale,
    validate_timezone,
    validate_user_agent,
)

# ---------------------------------------------------------------------------
# validate_user_agent
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test__validate_user_agent__strips_surrounding_whitespace() -> None:
    assert validate_user_agent("  Mozilla/5.0  ") == "Mozilla/5.0"


@pytest.mark.unit
@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test__validate_user_agent__rejects_empty(value: str) -> None:
    with pytest.raises(ValueError, match="User-Agent"):
        validate_user_agent(value)


# ---------------------------------------------------------------------------
# validate_cpu_cores
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("value", [1, 8, 32])
def test__validate_cpu_cores__accepts_boundary_values(value: int) -> None:
    assert validate_cpu_cores(value) == value


@pytest.mark.unit
@pytest.mark.parametrize("value", [0, -1, 33, 100])
def test__validate_cpu_cores__rejects_out_of_range(value: int) -> None:
    with pytest.raises(ValueError, match="CPU cores"):
        validate_cpu_cores(value)


# ---------------------------------------------------------------------------
# validate_device_memory
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("value", [1, 2, 4, 8])
def test__validate_device_memory__accepts_allowed_values(value: int) -> None:
    assert validate_device_memory(value) == value


@pytest.mark.unit
@pytest.mark.parametrize("value", [0, 3, 16, -1])
def test__validate_device_memory__rejects_disallowed_values(value: int) -> None:
    with pytest.raises(ValueError, match="Device memory"):
        validate_device_memory(value)


# ---------------------------------------------------------------------------
# validate_timezone
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test__validate_timezone__accepts_known_iana_zone() -> None:
    assert validate_timezone("America/New_York") == "America/New_York"


@pytest.mark.unit
def test__validate_timezone__rejects_unknown_zone() -> None:
    with pytest.raises(ValueError, match="Unknown IANA timezone"):
        validate_timezone("Mars/Olympus_Mons")


# ---------------------------------------------------------------------------
# validate_locale
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("value", ["en", "en-US", "ru-RU", "fr"])
def test__validate_locale__accepts_matching_pattern(value: str) -> None:
    assert validate_locale(value) == value


@pytest.mark.unit
@pytest.mark.parametrize("value", ["EN_us", "english", "en-us", "e", "en-USA", ""])
def test__validate_locale__rejects_non_matching_pattern(value: str) -> None:
    with pytest.raises(ValueError, match="Locale"):
        validate_locale(value)


# ---------------------------------------------------------------------------
# build_label
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test__build_label__full_effective_fingerprint_matches_expected_format() -> None:
    effective = EffectiveFingerprint(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
        ),
        cpu_cores=8,
        device_memory=8,
        timezone="America/New_York",
        locale="en-US",
    )

    assert build_label(effective) == "Mac · Chrome · 8 ядер / 8 ГБ"


@pytest.mark.unit
def test__build_label__all_none_values_uses_placeholder() -> None:
    values = FingerprintValues(
        user_agent=None, cpu_cores=None, device_memory=None, timezone=None, locale=None
    )

    assert build_label(values) == "? ядер / ? ГБ"


@pytest.mark.unit
def test__build_label__partial_values_omits_missing_platform_browser() -> None:
    values = FingerprintValues(
        user_agent=None, cpu_cores=4, device_memory=2, timezone=None, locale=None
    )

    assert build_label(values) == "4 ядер / 2 ГБ"


@pytest.mark.unit
def test__build_label__is_deterministic_for_same_input() -> None:
    values = FingerprintValues(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0 Safari/537.36",
        cpu_cores=16,
        device_memory=4,
        timezone="Europe/Moscow",
        locale="ru-RU",
    )

    assert build_label(values) == build_label(values)
    assert build_label(values) == "Windows · Chrome · 16 ядер / 4 ГБ"


# ---------------------------------------------------------------------------
# build_navigator_init_script
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test__build_navigator_init_script__carries_exact_integers() -> None:
    script = build_navigator_init_script(cpu_cores=6, device_memory=4)

    assert "hardwareConcurrency" in script
    assert "deviceMemory" in script
    assert "() => 6" in script
    assert "() => 4" in script


@pytest.mark.unit
def test__build_navigator_init_script__defines_both_navigator_properties() -> None:
    script = build_navigator_init_script(cpu_cores=8, device_memory=8)

    assert script.count("Object.defineProperty(navigator, 'hardwareConcurrency'") == 1
    assert script.count("Object.defineProperty(navigator, 'deviceMemory'") == 1
