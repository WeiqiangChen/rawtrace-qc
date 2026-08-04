"""Typed models shared across extraction and reporting services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """Store the trace artifacts produced by an extraction.

    The optional paths are absent when the corresponding MS-level artifact was
    not selected or is not present in the acquisition.
    """

    ms1_path: Path | None = None
    msn_path: Path | None = None
