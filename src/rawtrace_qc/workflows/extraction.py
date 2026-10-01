"""Resolve and extract batches of vendor raw acquisitions."""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path

from rawtrace_qc.discovery import (
    DiscoveryCandidate,
    DiscoveryOptions,
    DiscoveryScope,
    Vendor,
    discover,
    validate_path,
)
from rawtrace_qc.errors import (
    ConfigurationError,
    DiscoveryError,
    ThermoHelperError,
    ThermoHelperLicenseError,
    ThermoHelperNotFoundError,
    ThermoHelperVersionError,
    UnsupportedPlatformError,
)
from rawtrace_qc.extractors.bruker import BrukerExtractor
from rawtrace_qc.extractors.protocol import Extractor, PrecisionMode
from rawtrace_qc.extractors.thermo import ThermoExtractor
from rawtrace_qc.models import ExtractionResult
from rawtrace_qc.thermo.locator import (
    ThermoHelperState,
    ThermoHelperStatus,
    get_thermo_helper_status,
)


class ExtractionOutcomeStatus(StrEnum):
    """Describe the result of extracting one discovered acquisition."""

    SUCCEEDED = "succeeded"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ExtractionDiscoveryIssue:
    """Describe an input path that could not be classified or fully scanned."""

    path: Path
    message: str


@dataclass(frozen=True, slots=True)
class BatchExtractionOutcome:
    """Store the extraction result or reason for one discovered candidate."""

    candidate: DiscoveryCandidate
    status: ExtractionOutcomeStatus
    result: ExtractionResult | None = None
    error: Exception | None = None

    @property
    def reason(self) -> str | None:
        """Return the failure or skip reason, when present."""
        return str(self.error) if self.error is not None else None


@dataclass(frozen=True, slots=True)
class BatchExtractionResult:
    """Collect candidate outcomes and discovery issues for a batch."""

    outcomes: tuple[BatchExtractionOutcome, ...]
    discovery_issues: tuple[ExtractionDiscoveryIssue, ...]

    @property
    def exit_code(self) -> int:
        """Return zero only when every candidate succeeded and discovery was clean."""
        has_unsuccessful_outcome = any(
            outcome.status is not ExtractionOutcomeStatus.SUCCEEDED
            for outcome in self.outcomes
        )
        return int(has_unsuccessful_outcome or bool(self.discovery_issues))


def extract_batch(
    paths: Iterable[Path],
    *,
    recursive: bool = False,
    output_directory: Path | None = None,
    precision_mode: PrecisionMode = "low",
    select_ms1: bool = True,
    select_msn: bool = True,
    discovery_options: DiscoveryOptions | None = None,
) -> BatchExtractionResult:
    """Discover and extract each acquisition supplied directly or by directory.

    Each path is first validated as one complete acquisition. If it is not an
    acquisition, the path is scanned as a directory using the requested scope.
    Thermo helper readiness is checked once when the resolved batch contains
    Thermo candidates; an unavailable helper skips those candidates without
    preventing Bruker candidates from being processed.

    Args:
        paths: One or more acquisition paths or directories to scan.
        recursive: If True, scan directory descendants. Defaults to False.
        output_directory: Optional shared output directory. Defaults to each
            acquisition's parent directory.
        precision_mode: `low` for float32 trace values or `high` for float64.
            Defaults to `low`.
        select_ms1: If True (default), write the MS1 artifact when available.
        select_msn: If True (default), write the MSn artifact when available.
        discovery_options: Optional discovery thresholds and clock. The scope
            is controlled by `recursive`.

    Returns:
        Candidate outcomes and separate input-classification or traversal issues.

    Raises:
        ConfigurationError: If no input paths are supplied.
    """
    input_paths = tuple(Path(path).expanduser().absolute() for path in paths)
    if not input_paths:
        raise ConfigurationError("At least one input path is required.")

    selected_options = discovery_options or DiscoveryOptions()
    scan_options = replace(
        selected_options,
        scope=DiscoveryScope.RECURSIVE if recursive else DiscoveryScope.DIRECT,
    )
    candidates: list[DiscoveryCandidate] = []
    discovery_issues: list[ExtractionDiscoveryIssue] = []
    seen_candidates: set[str] = set()

    for input_path in input_paths:
        candidate = validate_path(input_path, scan_options)
        if candidate is not None:
            _append_candidate(candidate, candidates, seen_candidates)
            continue

        try:
            discovery_result = discover(input_path, scan_options)
        except DiscoveryError as error:
            discovery_issues.append(ExtractionDiscoveryIssue(input_path, str(error)))
            continue

        discovery_issues.extend(
            ExtractionDiscoveryIssue(issue.path, issue.message)
            for issue in discovery_result.issues
        )
        if not discovery_result.candidates:
            discovery_issues.append(
                ExtractionDiscoveryIssue(
                    input_path,
                    "No supported complete acquisitions were found.",
                )
            )
        for discovered_candidate in discovery_result.candidates:
            _append_candidate(discovered_candidate, candidates, seen_candidates)

    thermo_candidates = [
        candidate for candidate in candidates if candidate.vendor == Vendor.THERMO
    ]
    thermo_helper_error = _thermo_helper_error() if thermo_candidates else None

    extractor_instances: dict[str, Extractor] = {}
    outcomes: list[BatchExtractionOutcome] = []
    for candidate in candidates:
        if candidate.vendor == Vendor.THERMO and thermo_helper_error is not None:
            outcomes.append(
                BatchExtractionOutcome(
                    candidate,
                    ExtractionOutcomeStatus.SKIPPED,
                    error=thermo_helper_error,
                )
            )
            continue

        try:
            extractor = _get_extractor(candidate.vendor, extractor_instances)
            extraction_result = extractor.extract(
                candidate.path,
                output_directory=output_directory,
                precision_mode=precision_mode,
                select_ms1=select_ms1,
                select_msn=select_msn,
            )
        except Exception as error:
            outcomes.append(
                BatchExtractionOutcome(
                    candidate,
                    ExtractionOutcomeStatus.FAILED,
                    error=error,
                )
            )
        else:
            outcomes.append(
                BatchExtractionOutcome(
                    candidate,
                    ExtractionOutcomeStatus.SUCCEEDED,
                    result=extraction_result,
                )
            )

    return BatchExtractionResult(tuple(outcomes), tuple(discovery_issues))


def _append_candidate(
    candidate: DiscoveryCandidate,
    candidates: list[DiscoveryCandidate],
    seen_candidates: set[str],
) -> None:
    candidate_key = os.path.normcase(os.path.abspath(candidate.path))
    if candidate_key not in seen_candidates:
        candidates.append(candidate)
        seen_candidates.add(candidate_key)


def _get_extractor(
    vendor: str,
    extractor_instances: dict[str, Extractor],
) -> Extractor:
    if vendor not in extractor_instances:
        if vendor == Vendor.BRUKER:
            extractor_instances[vendor] = BrukerExtractor()
        elif vendor == Vendor.THERMO:
            extractor_instances[vendor] = ThermoExtractor()
        else:
            raise ConfigurationError(
                f"No extractor is registered for vendor {vendor!r}."
            )
    return extractor_instances[vendor]


def _thermo_helper_error() -> Exception | None:
    try:
        status = get_thermo_helper_status()
    except Exception as error:
        return error
    if status.is_ready:
        return None
    return _status_error(status)


def _status_error(status: ThermoHelperStatus) -> ThermoHelperError:
    error_types: dict[ThermoHelperState, type[ThermoHelperError]] = {
        ThermoHelperState.NOT_INSTALLED: ThermoHelperNotFoundError,
        ThermoHelperState.UNLICENSED: ThermoHelperLicenseError,
        ThermoHelperState.INVALID_VERSION: ThermoHelperVersionError,
        ThermoHelperState.UNSUPPORTED_PLATFORM: UnsupportedPlatformError,
    }
    error_type = error_types.get(status.state, ThermoHelperError)
    return error_type(status.message)
