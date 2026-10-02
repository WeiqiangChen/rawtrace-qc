"""Batch raw-acquisition extraction command."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Literal

from cyclopts import Parameter

from rawtrace_qc.cli.errors import print_cli_error
from rawtrace_qc.errors import RawtraceError
from rawtrace_qc.workflows import (
    BatchExtractionResult,
    ExtractionOutcomeStatus,
    extract_batch,
)


def extract(
    paths: Annotated[
        list[Path], Parameter(name="PATH", consume_multiple=True, negative_iterable=())
    ],
    recursive: Annotated[bool, Parameter(negative_bool=())] = False,
    output_dir: Path | None = None,
    precision: Literal["low", "high"] = "low",
    ms1: Annotated[bool, Parameter(negative_bool=())] = False,
    msn: Annotated[bool, Parameter(negative_bool=())] = False,
) -> int:
    """Extract scan traces from acquisition paths or directories.

    With neither MS-level flag, both levels are selected. Setting both flags
    also selects both levels.

    Args:
        paths: Acquisition files, directories, or glob patterns to scan.
        recursive: If True, scan source directories recursively. Defaults to False.
        output_dir: Optional output directory shared by all candidates.
        precision: Trace precision, either `low` or `high`. Defaults to `low`.
        ms1: If True, extract only MS1 unless `msn` is also True. Defaults to False.
        msn: If True, extract only MSn unless `ms1` is also True. Defaults to False.

    Returns:
        Exit code zero only when all candidates succeed and there are no
        discovery issues.
    """
    select_both_levels = not ms1 and not msn
    try:
        result = extract_batch(
            paths,
            recursive=recursive,
            output_directory=output_dir,
            precision_mode=precision,
            select_ms1=ms1 or select_both_levels,
            select_msn=msn or select_both_levels,
        )
    except RawtraceError as error:
        print_cli_error(error)
        return 1

    _print_batch_result(result)
    return result.exit_code


def _print_batch_result(result: BatchExtractionResult) -> None:
    print("Extraction outcomes:")
    if not result.outcomes:
        print("  No acquisition candidates were extracted.")
    for outcome in result.outcomes:
        print(f"  {outcome.status.value}: {outcome.candidate.path}")
        if outcome.error is not None:
            print_cli_error(
                outcome.error,
                thermo=outcome.candidate.vendor == "thermo",
            )
        elif outcome.result is not None:
            if outcome.result.ms1_path is not None:
                print(f"    MS1: {outcome.result.ms1_path}")
            if outcome.result.msn_path is not None:
                print(f"    MSn: {outcome.result.msn_path}")

    if result.discovery_issues:
        print("Discovery issues:", file=sys.stderr)
        for issue in result.discovery_issues:
            print(f"  {issue.path}: {issue.message}", file=sys.stderr)

    succeeded = sum(
        outcome.status is ExtractionOutcomeStatus.SUCCEEDED
        for outcome in result.outcomes
    )
    skipped = sum(
        outcome.status is ExtractionOutcomeStatus.SKIPPED for outcome in result.outcomes
    )
    failed = sum(
        outcome.status is ExtractionOutcomeStatus.FAILED for outcome in result.outcomes
    )
    print(
        f"Summary: {succeeded} succeeded, {skipped} skipped, {failed} failed, "
        f"{len(result.discovery_issues)} discovery issue(s)."
    )
