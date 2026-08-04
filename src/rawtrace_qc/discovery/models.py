"""Typed models used by the vendor-aware discovery workflow."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from rawtrace_qc.errors import ConfigurationError


class DiscoveryScope(StrEnum):
    """Select whether discovery examines direct children or descendants."""

    DIRECT = "direct"
    RECURSIVE = "recursive"


@dataclass(frozen=True, slots=True)
class TraversalIssue:
    """Describe a filesystem problem encountered below the source directory."""

    path: Path
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class TraversalTree:
    """Store accessible entries and issues found during filesystem traversal."""

    files: tuple[Path, ...] = ()
    directories: tuple[Path, ...] = ()
    issues: tuple[TraversalIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class DiscoveryCandidate:
    """Describe a valid acquisition identified by a vendor detector."""

    path: Path
    vendor: str
    format: str


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    """Return valid candidates together with non-fatal traversal issues."""

    candidates: tuple[DiscoveryCandidate, ...] = ()
    issues: tuple[TraversalIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class DiscoveryOptions:
    """Configure traversal scope, vendor selection, validation thresholds, and time."""

    scope: DiscoveryScope = DiscoveryScope.DIRECT
    vendors: frozenset[str] | None = None
    min_size_bytes: int = 1024 * 1024
    min_age_seconds: float = 600
    clock: Callable[[], float] = time.time

    def __post_init__(self) -> None:
        """Reject invalid vendor filters and negative thresholds."""
        if self.vendors is not None and any(
            not isinstance(vendor, str) or not vendor.strip() for vendor in self.vendors
        ):
            raise ConfigurationError("Vendor filters must contain non-empty strings.")
        if self.min_size_bytes < 0:
            raise ConfigurationError(
                f"Minimum size {self.min_size_bytes!r} must be non-negative."
            )
        if self.min_age_seconds < 0:
            raise ConfigurationError(
                f"Minimum age {self.min_age_seconds!r} must be non-negative."
            )
