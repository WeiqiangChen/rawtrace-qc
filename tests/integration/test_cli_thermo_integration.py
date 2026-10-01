"""Integration tests for the Thermo CLI commands against a real helper binary."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from rawtrace_qc.cli import main
from rawtrace_qc.thermo.specification import THERMO_HELPER_SPECIFICATION

pytestmark = pytest.mark.network


def _create_unlicensed_helper_copy(source_executable: Path, destination_directory: Path) -> Path:
    source_directory = source_executable.parent
    shutil.copytree(
        source_directory,
        destination_directory,
        ignore=shutil.ignore_patterns(THERMO_HELPER_SPECIFICATION.license_marker_name),
    )
    return destination_directory / source_executable.name


class TestCliThermoIntegration:
    def test_status_reports_ready_for_real_licensed_helper(
        self,
        thermo_helper_executable: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        result = main(["thermo", "status", "--helper-path", str(thermo_helper_executable)])

        output = capsys.readouterr().out
        assert result == 0
        assert "Thermo helper status: ready" in output
        assert "is ready" in output

    def test_status_reports_unlicensed_when_license_marker_is_missing(
        self,
        thermo_helper_executable: Path,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        unlicensed_executable = _create_unlicensed_helper_copy(
            thermo_helper_executable,
            tmp_path / "unlicensed-helper",
        )

        result = main(["thermo", "status", "--helper-path", str(unlicensed_executable)])

        output = capsys.readouterr().out
        assert result == 1
        assert "Thermo helper status: unlicensed" in output
        assert "rawtrace-qc thermo accept-license" in output

    def test_accept_license_displays_terms_and_enables_ready_status(
        self,
        thermo_helper_executable: Path,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        unlicensed_executable = _create_unlicensed_helper_copy(
            thermo_helper_executable,
            tmp_path / "unlicensed-helper",
        )
        marker_path = unlicensed_executable.parent / THERMO_HELPER_SPECIFICATION.license_marker_name
        assert not marker_path.exists()

        accept_result = main(["thermo", "accept-license", "--helper-path", str(unlicensed_executable)])

        accept_output = capsys.readouterr().out
        assert accept_result == 0
        assert "The following Thermo license terms will be accepted by this command:" in accept_output
        assert "Thermo license acceptance is recorded for this helper installation." in accept_output
        assert marker_path.is_file()

        status_result = main(["thermo", "status", "--helper-path", str(unlicensed_executable)])

        status_output = capsys.readouterr().out
        assert status_result == 0
        assert "Thermo helper status: ready" in status_output
