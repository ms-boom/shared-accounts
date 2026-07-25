"""Browser fingerprint domain module — value objects, validators, label and JS builder.

Pure and dependency-free: this module must never import `Settings`, SQLAlchemy,
Patchright, or anything from `src/bot/`. It is the single source of truth for the
per-field predicates, reused unchanged by `core.config.Settings` (defaults) and by
the FSM step validators in the presentation layer, so the two callers can never
diverge on what counts as a valid value.
"""

import re
from dataclasses import dataclass
from zoneinfo import available_timezones

_MIN_CPU_CORES = 1
_MAX_CPU_CORES = 32
_ALLOWED_DEVICE_MEMORY = frozenset({1, 2, 4, 8})
_LOCALE_PATTERN = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")


@dataclass(frozen=True)
class FingerprintValues:
    """Stored/draft fingerprint fields.

    Any field may be `None`, meaning "no override for this field" — resolution
    falls back to the default profile per field (see `merge` in the resolution
    service).
    """

    user_agent: str | None
    cpu_cores: int | None
    device_memory: int | None
    timezone: str | None
    locale: str | None


@dataclass(frozen=True)
class EffectiveFingerprint:
    """Fully resolved fingerprint, ready to apply to a browser context.

    No field is ever `None` — resolution always fills every field from the
    default profile before this object is built.
    """

    user_agent: str
    cpu_cores: int
    device_memory: int
    timezone: str
    locale: str


@dataclass(frozen=True)
class FingerprintView:
    """Display-ready fingerprint for the `/fingerprint` view card."""

    effective: EffectiveFingerprint
    source: dict[str, str]
    shared_session_count: int
    label: str | None


def validate_user_agent(value: str) -> str:
    """Normalize and validate a User-Agent string.

    Args:
        value: raw User-Agent candidate.

    Returns:
        The stripped, non-empty User-Agent.

    Raises:
        ValueError: if the value is empty after stripping.
    """
    normalized = value.strip()
    if not normalized:
        raise ValueError("User-Agent must not be empty")
    return normalized


def validate_cpu_cores(value: int) -> int:
    """Validate a `navigator.hardwareConcurrency` candidate.

    Args:
        value: candidate core count.

    Returns:
        The value unchanged, once validated.

    Raises:
        ValueError: if value is outside `1..32`.
    """
    if not (_MIN_CPU_CORES <= value <= _MAX_CPU_CORES):
        raise ValueError(
            f"CPU cores must be between {_MIN_CPU_CORES} and {_MAX_CPU_CORES}, "
            f"got {value}"
        )
    return value


def validate_device_memory(value: int) -> int:
    """Validate a `navigator.deviceMemory` candidate (browsers cap it at 8 GB).

    Args:
        value: candidate memory size in GB.

    Returns:
        The value unchanged, once validated.

    Raises:
        ValueError: if value is not one of `{1, 2, 4, 8}`.
    """
    if value not in _ALLOWED_DEVICE_MEMORY:
        allowed = sorted(_ALLOWED_DEVICE_MEMORY)
        raise ValueError(f"Device memory must be one of {allowed} GB, got {value}")
    return value


def validate_timezone(value: str) -> str:
    """Validate an IANA timezone name.

    Args:
        value: candidate timezone, e.g. `"America/New_York"`.

    Returns:
        The value unchanged, once validated.

    Raises:
        ValueError: if value is not a known IANA timezone.
    """
    if value not in available_timezones():
        raise ValueError(f"Unknown IANA timezone: '{value}'")
    return value


def validate_locale(value: str) -> str:
    """Validate a locale tag such as `"en"` or `"en-US"`.

    Args:
        value: candidate locale.

    Returns:
        The value unchanged, once validated.

    Raises:
        ValueError: if value does not match `xx` or `xx-XX`.
    """
    if not _LOCALE_PATTERN.match(value):
        raise ValueError(f"Locale must look like 'en' or 'en-US', got: '{value}'")
    return value


def build_navigator_init_script(cpu_cores: int, device_memory: int) -> str:
    """Build the JS snippet that overrides `navigator.hardwareConcurrency`/`deviceMemory`.

    Args:
        cpu_cores: already-validated core count (`1..32`).
        device_memory: already-validated memory size (`{1, 2, 4, 8}` GB).

    Returns:
        JS source suitable for `context.add_init_script`. Inputs are integers
        already validated by `validate_cpu_cores`/`validate_device_memory`, so
        interpolation here is injection-safe.
    """
    return (
        "Object.defineProperty(navigator, 'hardwareConcurrency', "
        f"{{ get: () => {cpu_cores} }});\n"
        "Object.defineProperty(navigator, 'deviceMemory', "
        f"{{ get: () => {device_memory} }});"
    )


_PLATFORM_MARKERS: tuple[tuple[str, str], ...] = (
    ("iPhone", "iPhone"),
    ("iPad", "iPad"),
    ("Android", "Android"),
    ("Macintosh", "Mac"),
    ("Windows", "Windows"),
    ("Linux", "Linux"),
)

_BROWSER_MARKERS: tuple[tuple[str, str], ...] = (
    ("Edg/", "Edge"),
    ("OPR/", "Opera"),
    ("Chrome/", "Chrome"),
    ("Firefox/", "Firefox"),
    ("Safari/", "Safari"),
)


def _detect_platform(user_agent: str) -> str | None:
    """Return a short platform name found in `user_agent`, or None."""
    for marker, name in _PLATFORM_MARKERS:
        if marker in user_agent:
            return name
    return None


def _detect_browser(user_agent: str) -> str | None:
    """Return a short browser name found in `user_agent`, or None."""
    for marker, name in _BROWSER_MARKERS:
        if marker in user_agent:
            return name
    return None


def build_label(values: FingerprintValues | EffectiveFingerprint) -> str:
    """Auto-generate a short, deterministic display label.

    Example: `"Mac · Chrome · 8 ядер / 8 ГБ"`. No free-form naming in v1 — the
    label is derived solely from the fingerprint fields, so it never diverges
    from the values it describes.

    Args:
        values: a `FingerprintValues` (possibly partial) or a fully resolved
            `EffectiveFingerprint`.

    Returns:
        The generated label. Missing fields render as `"?"`.
    """
    parts: list[str] = []
    if values.user_agent:
        platform = _detect_platform(values.user_agent)
        browser = _detect_browser(values.user_agent)
        parts.extend(p for p in (platform, browser) if p)

    cores = values.cpu_cores if values.cpu_cores is not None else "?"
    memory = values.device_memory if values.device_memory is not None else "?"
    parts.append(f"{cores} ядер / {memory} ГБ")

    return " · ".join(parts)
