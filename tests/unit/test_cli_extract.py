from __future__ import annotations

from pathlib import Path

import pytest
from rawtrace_qc.cli import extract as extract_cli_module
from rawtrace_qc.cli import main
from rawtrace_qc.discovery import DiscoveryCandidate, Vendor
from rawtrace_qc.errors import ThermoHelperNotFoundError
from rawtrace_qc.models import ExtractionResult
from rawtrace_qc.workflows import (
    BatchExtractionOutcome,
    BatchExtractionResult,
    ExtractionDiscoveryIssue,
    ExtractionOutcomeStatus,
)


class TestExtractCommand:
    def test_command_passes_options_to_library_and_renders_outcomes(self, tmp_path: Path, monkeypatch, capsys) -> None:
        raw_file = tmp_path / "sample.raw"
        second_raw_file = tmp_path / "second.raw"
        output_directory = tmp_path / "traces"
        candidate = DiscoveryCandidate(raw_file, Vendor.THERMO, "raw")
        batch_result = BatchExtractionResult(
            outcomes=(
                BatchExtractionOutcome(
                    candidate,
                    ExtractionOutcomeStatus.SUCCEEDED,
                    ExtractionResult(msn_path=output_directory / "sample.msn-trace.parquet"),
                ),
            ),
            discovery_issues=(),
        )
        calls: dict[str, object] = {}

        def fake_extract_batch(paths, **kwargs):
            calls["paths"] = paths
            calls.update(kwargs)
            return batch_result

        monkeypatch.setattr(extract_cli_module, "extract_batch", fake_extract_batch)

        result = main(
            [
                "extract",
                str(raw_file),
                str(second_raw_file),
                "--output-dir",
                str(output_directory),
                "--precision",
                "high",
                "--recursive",
                "--msn",
            ]
        )

        output = capsys.readouterr().out
        assert result == 0
        assert calls == {
            "paths": [raw_file, second_raw_file],
            "recursive": True,
            "output_directory": output_directory,
            "precision_mode": "high",
            "select_ms1": False,
            "select_msn": True,
        }
        assert "succeeded" in output
        assert "sample.msn-trace.parquet" in output

    @pytest.mark.parametrize(
        ("flags", "select_ms1", "select_msn"),
        [
            ([], True, True),
            (["--ms1"], True, False),
            (["--msn"], False, True),
            (["--ms1", "--msn"], True, True),
        ],
    )
    def test_ms_level_flags_select_expected_levels(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flags: list[str], select_ms1: bool, select_msn: bool
    ) -> None:
        raw_file = tmp_path / "sample.raw"
        calls: dict[str, object] = {}

        def fake_extract_batch(paths, **kwargs):
            calls.update(kwargs)
            return BatchExtractionResult(outcomes=(), discovery_issues=())

        monkeypatch.setattr(extract_cli_module, "extract_batch", fake_extract_batch)

        result = main(["extract", str(raw_file), *flags])

        assert result == 0
        assert calls["select_ms1"] is select_ms1
        assert calls["select_msn"] is select_msn

    def test_not_ready_thermo_skip_uses_shared_error_hints(self, tmp_path: Path, monkeypatch, capsys) -> None:
        candidate = DiscoveryCandidate(tmp_path / "sample.raw", Vendor.THERMO, "raw")
        batch_result = BatchExtractionResult(
            outcomes=(
                BatchExtractionOutcome(
                    candidate,
                    ExtractionOutcomeStatus.SKIPPED,
                    error=ThermoHelperNotFoundError("Thermo helper is not installed."),
                ),
            ),
            discovery_issues=(),
        )
        monkeypatch.setattr(extract_cli_module, "extract_batch", lambda *_args, **_kwargs: batch_result)

        result = main(["extract", str(candidate.path)])

        captured = capsys.readouterr()
        assert result == 1
        assert "skipped" in captured.out
        assert "Thermo helper is not installed." in captured.err
        assert "rawtrace-qc thermo install" in captured.err

    def test_discovery_issues_are_rendered_separately_and_fail_the_command(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        candidate = DiscoveryCandidate(tmp_path / "sample.raw", Vendor.THERMO, "raw")
        issue = ExtractionDiscoveryIssue(tmp_path / "unclassified", "No supported complete acquisitions were found.")
        batch_result = BatchExtractionResult(
            outcomes=(BatchExtractionOutcome(candidate, ExtractionOutcomeStatus.SUCCEEDED),),
            discovery_issues=(issue,),
        )
        monkeypatch.setattr(extract_cli_module, "extract_batch", lambda *_args, **_kwargs: batch_result)

        result = main(["extract", str(issue.path)])

        captured = capsys.readouterr()
        assert result == 1
        assert "succeeded" in captured.out
        assert "Discovery issues:" in captured.err
        assert str(issue.path) in captured.err
        assert issue.message in captured.err

    def test_root_help_lists_registered_subcommands(self, capsys) -> None:
        result = main(["--help"])

        output = capsys.readouterr().out
        assert result == 0
        assert "thermo" in output
        assert "extract" in output

    def test_extract_help_omits_negative_ms_level_flags(self, capsys) -> None:
        result = main(["extract", "--help"])

        output = capsys.readouterr().out
        assert result == 0
        assert "--ms1" in output
        assert "--msn" in output
        assert "--no-ms1" not in output
        assert "--no-msn" not in output
