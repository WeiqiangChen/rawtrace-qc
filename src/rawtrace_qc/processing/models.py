"""Typed models for report-ready trace tables."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

import pyarrow as pa

from rawtrace_qc.errors import ConfigurationError


class FaimsProcessingMode(StrEnum):
    """Select how FAIMS-bearing trace tables are partitioned."""

    SPLIT = "split"
    COMBINED = "combined"


@dataclass(frozen=True, slots=True)
class ProcessingOptions:
    """Configure how trace artifacts are partitioned for reporting."""

    ms_levels: tuple[int, ...] = (1, 2)
    faims_mode: FaimsProcessingMode = FaimsProcessingMode.SPLIT
    minimum_faims_percentage: float | None = None

    def __post_init__(self) -> None:
        """Validate processing options and normalize MS-level selection."""
        levels = tuple(self.ms_levels)
        if not levels or any(
            isinstance(level, bool) or not isinstance(level, int) or level < 1
            for level in levels
        ):
            raise ConfigurationError(
                f"Processing ms_levels must contain positive integers, got {levels!r}."
            )
        if len(set(levels)) != len(levels):
            raise ConfigurationError(
                f"Processing ms_levels must not contain duplicates, got {levels!r}."
            )
        try:
            faims_mode = FaimsProcessingMode(self.faims_mode)
        except (TypeError, ValueError) as error:
            raise ConfigurationError(
                f"Processing faims_mode {self.faims_mode!r} is invalid; "
                "choose 'split' or 'combined'."
            ) from error
        if self.minimum_faims_percentage is not None and (
            isinstance(self.minimum_faims_percentage, bool)
            or not isinstance(self.minimum_faims_percentage, (int, float))
            or not math.isfinite(float(self.minimum_faims_percentage))
            or not 0 <= self.minimum_faims_percentage <= 100
        ):
            raise ConfigurationError(
                "Processing minimum_faims_percentage must be None or a number "
                "between 0 and 100."
            )
        object.__setattr__(self, "ms_levels", levels)
        object.__setattr__(self, "faims_mode", faims_mode)
        if self.minimum_faims_percentage is not None:
            object.__setattr__(
                self,
                "minimum_faims_percentage",
                float(self.minimum_faims_percentage),
            )


@dataclass(frozen=True, slots=True)
class ProcessedTableMetadata:
    """Describe one report-ready table and its extraction provenance."""

    rawfile_name: str
    label: str
    source_id: str | None
    schema_version: str
    generator: str
    vendor: str
    ms_level_file: str
    extracted_at: str
    acquisition_start_time: str
    ms_level: int
    faims_cv: float | str | None
    row_granularity: str
    time_unit: str
    precision: str
    channels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProcessedTable:
    """Pair one report-ready Arrow table with its descriptive metadata."""

    table: pa.Table
    metadata: ProcessedTableMetadata
