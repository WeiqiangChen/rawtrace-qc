"""Integration tests for the public discovery workflow."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from rawtrace_qc.discovery import DiscoveryOptions, DiscoveryScope, Vendor, discover

NOW = datetime(2026, 8, 4, tzinfo=UTC).timestamp()


def _write_file(path: Path, size: int) -> None:
    path.write_bytes(b"x" * size)
    os.utime(path, (NOW - 601, NOW - 601))


def _write_bruker(path: Path) -> None:
    path.mkdir()
    _write_file(path / "metadata.tdf", 1)
    _write_file(path / "binary.tdf_bin", 1)


def test_discover_mixed_recursive_tree(tmp_path: Path) -> None:
    _write_file(tmp_path / "thermo.RAW", 1)
    _write_bruker(tmp_path / "bruker.D")
    nested = tmp_path / "nested"
    nested.mkdir()
    _write_file(nested / "nested.raw", 1)
    _write_file(tmp_path / "empty.raw", 0)

    result = discover(
        tmp_path,
        DiscoveryOptions(scope=DiscoveryScope.RECURSIVE, min_size_bytes=1, min_age_seconds=600, clock=lambda: NOW),
    )

    assert [candidate.path.name for candidate in result.candidates] == ["bruker.D", "nested.raw", "thermo.RAW"]
    assert [candidate.vendor for candidate in result.candidates] == [Vendor.BRUKER, Vendor.THERMO, Vendor.THERMO]
    assert result.issues == ()
