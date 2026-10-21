"""Cache extracted trace artifacts for the desktop workflow."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from rawtrace_qc.discovery import DiscoveryCandidate
from rawtrace_qc.errors import ArtifactValidationError, ConfigurationError
from rawtrace_qc.extractors.protocol import PrecisionMode
from rawtrace_qc.models import ExtractionResult
from rawtrace_qc.traces import load_trace

_CACHE_OUTPUT_NAME = "trace"


class CacheExtractor(Protocol):
    """Define the extractor operation required by `TraceCache`."""

    def extract(
        self,
        input_path: Path,
        output_directory: Path | None = None,
        output_name: str | None = None,
        precision_mode: PrecisionMode = "low",
        *,
        select_ms1: bool = True,
        select_msn: bool = True,
    ) -> ExtractionResult:
        """Extract trace artifacts into the requested output directory."""


@dataclass(frozen=True, slots=True)
class CacheResult:
    """Store extraction paths and whether they were loaded from cache."""

    extraction: ExtractionResult
    cache_hit: bool


class TraceCache:
    """Store validated trace artifacts under content-metadata cache keys."""

    def __init__(self, directory: Path) -> None:
        """Create a cache rooted at `directory`."""
        self.directory = Path(directory).expanduser().resolve()

    def extract(
        self,
        candidate: DiscoveryCandidate,
        extractor: CacheExtractor,
        *,
        precision_mode: PrecisionMode = "low",
        select_ms1: bool = True,
        select_msn: bool = True,
    ) -> CacheResult:
        """Load a valid cached extraction or create one for `candidate`.

        The cache key includes the resolved source path, source metadata,
        vendor, extractor class, precision, and selected MS levels. Existing
        cache artifacts are loaded through `load_trace()` so incomplete or
        incompatible files are treated as cache misses.

        Args:
            candidate: Validated raw acquisition to extract.
            extractor: Vendor extractor used to create trace artifacts.
            precision_mode: Trace precision passed to the extractor.
            select_ms1: Whether the MS1 artifact is requested.
            select_msn: Whether the MSn artifact is requested.

        Returns:
            Cached or freshly extracted artifact paths and cache-hit state.

        Raises:
            ConfigurationError: If the source signature cannot be read.
            ArtifactValidationError: If a fresh extractor returns an invalid
                artifact.
        """
        source = candidate.path.expanduser().resolve()
        cache_directory = self.directory / _cache_key(
            source,
            candidate,
            extractor,
            precision_mode,
            select_ms1,
            select_msn,
        )
        cached = _read_cached_result(
            source,
            cache_directory,
            select_ms1=select_ms1,
            select_msn=select_msn,
        )
        if cached is not None:
            return CacheResult(cached, True)

        result = extractor.extract(
            source,
            output_directory=cache_directory,
            output_name=_CACHE_OUTPUT_NAME,
            precision_mode=precision_mode,
            select_ms1=select_ms1,
            select_msn=select_msn,
        )
        _validate_result(result)
        return CacheResult(result, False)


def _cache_key(
    source: Path,
    candidate: DiscoveryCandidate,
    extractor: CacheExtractor,
    precision_mode: PrecisionMode,
    select_ms1: bool,
    select_msn: bool,
) -> str:
    digest = hashlib.sha256()
    _update_digest(digest, str(source).casefold())
    _update_digest(digest, candidate.vendor)
    _update_digest(digest, candidate.format)
    extractor_type = type(extractor)
    _update_digest(
        digest,
        f"{extractor_type.__module__}.{extractor_type.__qualname__}",
    )
    _update_digest(digest, precision_mode)
    _update_digest(digest, str(select_ms1))
    _update_digest(digest, str(select_msn))
    try:
        source_metadata = source.stat()
        _update_digest(digest, str(source_metadata.st_size))
        _update_digest(digest, str(source_metadata.st_mtime_ns))
        if source.is_dir():
            for member in sorted(
                source.iterdir(), key=lambda item: item.name.casefold()
            ):
                if not member.is_file():
                    continue
                metadata = member.stat()
                _update_digest(digest, member.name.casefold())
                _update_digest(digest, str(metadata.st_size))
                _update_digest(digest, str(metadata.st_mtime_ns))
    except OSError as error:
        raise ConfigurationError(
            f"Could not read source metadata for cache key {source}: {error}."
        ) from error
    return digest.hexdigest()[:16]


def _read_cached_result(
    source: Path,
    cache_directory: Path,
    *,
    select_ms1: bool,
    select_msn: bool,
) -> ExtractionResult | None:
    expected = {
        "ms1": cache_directory / f"{_CACHE_OUTPUT_NAME}.ms1-trace.parquet",
        "msn": cache_directory / f"{_CACHE_OUTPUT_NAME}.msn-trace.parquet",
    }
    requested = {
        level: path
        for level, path in expected.items()
        if (level == "ms1" and select_ms1) or (level == "msn" and select_msn)
    }
    if not requested or any(not path.is_file() for path in requested.values()):
        return None
    try:
        for path in requested.values():
            load_trace(path)
    except ArtifactValidationError:
        return None
    return ExtractionResult(
        ms1_path=requested.get("ms1"),
        msn_path=requested.get("msn"),
    )


def _validate_result(result: ExtractionResult) -> None:
    for path in (result.ms1_path, result.msn_path):
        if path is None:
            continue
        try:
            load_trace(path)
        except ArtifactValidationError:
            raise


def _update_digest(digest: hashlib._Hash, value: str) -> None:
    digest.update(value.encode("utf-8"))
    digest.update(b"\0")
