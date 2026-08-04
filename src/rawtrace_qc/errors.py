"""Exception types shared by rawtrace-qc public APIs."""


class RawtraceError(Exception):
    """Base class for expected rawtrace-qc errors."""


class ConfigurationError(RawtraceError):
    """Raise when a rawtrace-qc option or configuration is invalid."""


class ArtifactValidationError(RawtraceError):
    """Raise when a generated or loaded trace artifact violates its contract."""
