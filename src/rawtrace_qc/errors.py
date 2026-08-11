"""Exception types shared by rawtrace-qc public APIs."""

from __future__ import annotations


class RawtraceError(Exception):
    """Base class for expected rawtrace-qc errors."""


class ConfigurationError(RawtraceError):
    """Raise when a rawtrace-qc option or configuration is invalid."""


class DiscoveryError(RawtraceError):
    """Raise when the discovery source cannot be traversed."""


class ArtifactValidationError(RawtraceError):
    """Raise when a generated or loaded trace artifact violates its contract."""


class ProcessingError(RawtraceError):
    """Raise when trace artifacts cannot be prepared for reporting."""


class ReportError(RawtraceError):
    """Raise when report data or HTML cannot be created."""
