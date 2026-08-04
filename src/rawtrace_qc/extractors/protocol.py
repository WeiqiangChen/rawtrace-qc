"""Structural interface shared by raw-file extractors."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Protocol

from rawtrace_qc.models import ExtractionResult

PrecisionMode = Literal["low", "high"]


class Extractor(Protocol):
    """Define the common extraction operation for supported vendors."""

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
        """Extract selected scan levels into schema-v1 Parquet artifacts."""
