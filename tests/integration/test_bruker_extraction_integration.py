from __future__ import annotations

from pathlib import Path

from rawtrace_qc.extractors import BrukerExtractor
from rawtrace_qc.traces import load_trace


def test_bruker_extraction_produces_loadable_trace_artifacts(bruker_fixture: Path, tmp_path: Path) -> None:
    result = BrukerExtractor().extract(
        bruker_fixture,
        output_directory=tmp_path / "traces",
    )

    assert result.ms1_path is not None
    assert result.msn_path is not None
    assert load_trace(result.ms1_path).metadata["vendor"] == "bruker"
    assert load_trace(result.msn_path).metadata["ms_level_file"] == "msn"
