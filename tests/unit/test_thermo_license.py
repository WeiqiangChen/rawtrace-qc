"""Unit tests for displaying and accepting the Thermo license agreement."""

from __future__ import annotations

from pathlib import Path

import pytest
from rawtrace_qc import environment
from rawtrace_qc.errors import ThermoHelperLicenseError
from rawtrace_qc.thermo import THERMO_LICENSE_MARKER_NAME, accept_thermo_license, get_thermo_license_text
from tests.support.mock_helper import MockThermoHelper, create_mock_helper_file


@pytest.fixture(autouse=True)
def mock_windows_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(environment, "get_platform", lambda: "win32")


class TestGetThermoLicenseText:
    def test_returns_license_text_without_accepting_terms(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        executable = create_mock_helper_file(tmp_path)
        license_text = "Thermo agreement\nAdditional terms\n"
        mock_runner = MockThermoHelper(license_text=license_text)
        monkeypatch.setattr("rawtrace_qc.thermo.locator.execute_helper_process", mock_runner)

        result = get_thermo_license_text(executable)

        assert result == license_text
        assert not (tmp_path / THERMO_LICENSE_MARKER_NAME).exists()
        assert mock_runner.commands_run == [
            [str(executable.resolve()), "--version"],
            [str(executable.resolve()), "--thermo-license"],
        ]

    def test_raises_when_helper_fails_to_display_license_text(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        executable = create_mock_helper_file(tmp_path)
        mock_runner = MockThermoHelper(license_text_exit_code=1, stderr="license output unavailable")
        monkeypatch.setattr("rawtrace_qc.thermo.locator.execute_helper_process", mock_runner)

        with pytest.raises(ThermoHelperLicenseError, match="failed with exit code 1"):
            get_thermo_license_text(executable)

    def test_raises_when_helper_returns_empty_license_text(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        executable = create_mock_helper_file(tmp_path)
        mock_runner = MockThermoHelper(license_text="")
        monkeypatch.setattr("rawtrace_qc.thermo.locator.execute_helper_process", mock_runner)

        with pytest.raises(ThermoHelperLicenseError, match="returned empty license text"):
            get_thermo_license_text(executable)


class TestAcceptThermoLicense:
    def test_accepts_terms_and_confirms_the_install_marker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        executable = create_mock_helper_file(tmp_path)
        mock_runner = MockThermoHelper()
        monkeypatch.setattr("rawtrace_qc.thermo.locator.execute_helper_process", mock_runner)

        accept_thermo_license(executable)

        assert (tmp_path / THERMO_LICENSE_MARKER_NAME).is_file()
        assert mock_runner.commands_run == [
            [str(executable.resolve()), "--version"],
            [str(executable.resolve()), "--agree-to-terms"],
        ]

    def test_raises_when_helper_exits_abnormally(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        executable = create_mock_helper_file(tmp_path)
        mock_runner = MockThermoHelper(agreement_exit_code=1, stderr="agreement failed")
        monkeypatch.setattr("rawtrace_qc.thermo.locator.execute_helper_process", mock_runner)

        with pytest.raises(ThermoHelperLicenseError, match="failed with exit code 1"):
            accept_thermo_license(executable)

        assert not (tmp_path / THERMO_LICENSE_MARKER_NAME).exists()

    def test_raises_when_successful_helper_does_not_create_marker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        executable = create_mock_helper_file(tmp_path)
        mock_runner = MockThermoHelper(writes_license_marker=False)
        monkeypatch.setattr("rawtrace_qc.thermo.locator.execute_helper_process", mock_runner)

        with pytest.raises(ThermoHelperLicenseError, match="did not create the expected license marker"):
            accept_thermo_license(executable)

    def test_is_idempotent_when_this_installation_is_already_accepted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        executable = create_mock_helper_file(tmp_path, license_accepted=True)
        mock_runner = MockThermoHelper(os_error=OSError("must not run"))
        monkeypatch.setattr("rawtrace_qc.thermo.locator.execute_helper_process", mock_runner)

        accept_thermo_license(executable)

        assert mock_runner.commands_run == []

    def test_accepts_only_the_selected_installation(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        first_install = tmp_path / "install-one"
        second_install = tmp_path / "install-two"
        first_executable = create_mock_helper_file(first_install)
        create_mock_helper_file(second_install)
        mock_runner = MockThermoHelper()
        monkeypatch.setattr("rawtrace_qc.thermo.locator.execute_helper_process", mock_runner)

        accept_thermo_license(first_executable)

        assert (first_install / THERMO_LICENSE_MARKER_NAME).is_file()
        assert not (second_install / THERMO_LICENSE_MARKER_NAME).exists()
