"""Persistent configuration for the rawtrace-qc desktop application."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rawtrace_qc.discovery import DiscoveryOptions, DiscoveryScope
from rawtrace_qc.errors import ConfigurationError
from rawtrace_qc.gui.patterns import FilenamePattern, PatternMode


@dataclass(frozen=True, slots=True)
class ThermoToolSettings:
    """Configure the optional ThermScanHeaderExtractor installation."""

    download_url: str | None = None
    sha256: str | None = None
    executable_path: Path | None = None
    executable_name: str = "ThermScanHeaderExtractor.exe"

    def __post_init__(self) -> None:
        """Validate helper download and executable settings."""
        if self.download_url is not None and (
            not isinstance(self.download_url, str) or not self.download_url.strip()
        ):
            raise ConfigurationError(
                "Thermo helper download_url must be None or a non-empty URL."
            )
        if self.sha256 is not None:
            if not isinstance(self.sha256, str) or len(self.sha256) != 64:
                raise ConfigurationError(
                    "Thermo helper sha256 must be a 64-character hexadecimal digest."
                )
            try:
                int(self.sha256, 16)
            except ValueError as error:
                raise ConfigurationError(
                    f"Thermo helper sha256 must be hexadecimal; got {self.sha256!r}."
                ) from error
        if not isinstance(self.executable_name, str) or not (
            self.executable_name.strip()
        ):
            raise ConfigurationError(
                "Thermo helper executable_name must be a non-empty string."
            )
        if self.executable_path is not None:
            object.__setattr__(self, "executable_path", Path(self.executable_path))


@dataclass(frozen=True, slots=True)
class GuiSettings:
    """Store persisted discovery, cache, report, and helper settings."""

    scope: DiscoveryScope = DiscoveryScope.DIRECT
    min_size_bytes: int = 1024 * 1024
    min_age_seconds: float = 600
    patterns: tuple[FilenamePattern, ...] = ()
    cache_directory: Path = field(
        default_factory=lambda: default_data_directory() / "cache"
    )
    report_directory: Path = field(
        default_factory=lambda: Path.home() / "rawtrace-qc-reports"
    )
    thermo: ThermoToolSettings = field(default_factory=ThermoToolSettings)

    def __post_init__(self) -> None:
        """Validate persisted values and normalize enum and path fields."""
        try:
            scope = DiscoveryScope(self.scope)
        except (TypeError, ValueError) as error:
            raise ConfigurationError(
                f"GUI discovery scope {self.scope!r} is invalid; choose 'direct' "
                "or 'recursive'."
            ) from error
        try:
            DiscoveryOptions(
                scope=scope,
                min_size_bytes=self.min_size_bytes,
                min_age_seconds=self.min_age_seconds,
            )
        except (TypeError, ValueError) as error:
            raise ConfigurationError(
                "GUI discovery thresholds must be non-negative numeric values."
            ) from error
        patterns = tuple(self.patterns)
        if any(not isinstance(pattern, FilenamePattern) for pattern in patterns):
            raise ConfigurationError(
                "GUI patterns must contain only FilenamePattern instances."
            )
        if not isinstance(self.thermo, ThermoToolSettings):
            raise ConfigurationError(
                "GUI thermo settings must be a ThermoToolSettings instance."
            )
        object.__setattr__(self, "scope", scope)
        object.__setattr__(self, "patterns", patterns)
        object.__setattr__(self, "cache_directory", Path(self.cache_directory))
        object.__setattr__(self, "report_directory", Path(self.report_directory))

    def discovery_options(self) -> DiscoveryOptions:
        """Return discovery options represented by this configuration."""
        return DiscoveryOptions(
            scope=self.scope,
            min_size_bytes=self.min_size_bytes,
            min_age_seconds=self.min_age_seconds,
        )


def default_data_directory() -> Path:
    """Return the platform-appropriate per-user rawtrace-qc data directory."""
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return root / "rawtrace-qc"


def default_config_path() -> Path:
    """Return the platform-appropriate GUI configuration path."""
    if os.name == "nt":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "rawtrace-qc" / "config.json"


def load_settings(path: Path | None = None) -> GuiSettings:
    """Load GUI settings from JSON, returning defaults for a missing file.

    Args:
        path: Configuration file path. If None (default), uses
            `default_config_path()`.

    Returns:
        Validated GUI settings.

    Raises:
        ConfigurationError: If the file cannot be decoded or contains invalid
            settings.
    """
    resolved_path = (path or default_config_path()).expanduser().resolve()
    if not resolved_path.exists():
        return GuiSettings()
    try:
        payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigurationError(
            f"Could not load GUI configuration {resolved_path}: {error}."
        ) from error
    try:
        return _settings_from_mapping(payload)
    except (TypeError, ValueError, KeyError) as error:
        raise ConfigurationError(
            f"GUI configuration {resolved_path} has an invalid structure: {error}."
        ) from error


def save_settings(settings: GuiSettings, path: Path | None = None) -> Path:
    """Write validated GUI settings to JSON and return the resolved path."""
    if not isinstance(settings, GuiSettings):
        raise ConfigurationError(
            f"Expected GuiSettings, got {type(settings).__name__!r}."
        )
    resolved_path = (path or default_config_path()).expanduser().resolve()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        resolved_path.write_text(
            json.dumps(_settings_to_mapping(settings), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError as error:
        raise ConfigurationError(
            f"Could not save GUI configuration {resolved_path}: {error}."
        ) from error
    return resolved_path


def _settings_from_mapping(payload: Any) -> GuiSettings:
    if not isinstance(payload, dict):
        raise TypeError("the root value must be an object")
    discovery = payload.get("discovery", {})
    if not isinstance(discovery, dict):
        raise TypeError("discovery must be an object")
    patterns_payload = payload.get("patterns", [])
    if not isinstance(patterns_payload, list):
        raise TypeError("patterns must be a list")
    patterns = tuple(
        FilenamePattern(
            name=item["name"],
            expression=item["expression"],
            mode=item.get("mode", PatternMode.INCLUDE),
        )
        for item in patterns_payload
        if isinstance(item, dict)
    )
    if len(patterns) != len(patterns_payload):
        raise TypeError("every pattern must be an object")
    thermo_payload = payload.get("thermo", {})
    if not isinstance(thermo_payload, dict):
        raise TypeError("thermo must be an object")
    executable_path = thermo_payload.get("executable_path")
    return GuiSettings(
        scope=discovery.get("scope", DiscoveryScope.DIRECT),
        min_size_bytes=discovery.get("min_size_bytes", 1024 * 1024),
        min_age_seconds=discovery.get("min_age_seconds", 600),
        patterns=patterns,
        cache_directory=Path(
            payload.get("cache_directory", default_data_directory() / "cache")
        ),
        report_directory=Path(
            payload.get("report_directory", Path.home() / "rawtrace-qc-reports")
        ),
        thermo=ThermoToolSettings(
            download_url=thermo_payload.get("download_url"),
            sha256=thermo_payload.get("sha256"),
            executable_path=Path(executable_path) if executable_path else None,
            executable_name=thermo_payload.get(
                "executable_name", "ThermScanHeaderExtractor.exe"
            ),
        ),
    )


def _settings_to_mapping(settings: GuiSettings) -> dict[str, Any]:
    return {
        "cache_directory": str(settings.cache_directory),
        "discovery": {
            "min_age_seconds": settings.min_age_seconds,
            "min_size_bytes": settings.min_size_bytes,
            "scope": settings.scope.value,
        },
        "patterns": [
            {
                "expression": pattern.expression,
                "mode": pattern.mode.value,
                "name": pattern.name,
            }
            for pattern in settings.patterns
        ],
        "report_directory": str(settings.report_directory),
        "thermo": {
            "download_url": settings.thermo.download_url,
            "executable_name": settings.thermo.executable_name,
            "executable_path": (
                None
                if settings.thermo.executable_path is None
                else str(settings.thermo.executable_path)
            ),
            "sha256": settings.thermo.sha256,
        },
    }
