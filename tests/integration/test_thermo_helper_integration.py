"""Integration test for installing and licensing the pinned Thermo helper."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from rawtrace_qc import environment
from rawtrace_qc.thermo import (
    THERMO_HELPER_SPECIFICATION,
    ThermoHelperState,
    accept_thermo_license,
    get_thermo_helper_status,
    install_thermo_helper,
    is_license_accepted,
    verify_helper_version,
)
from tests.support.network import urlopen_or_skip

pytestmark = pytest.mark.skipif(
    os.environ.get("RAWTRACE_QC_RUN_THERMO_INSTALL_INTEGRATION") != "1",
    reason=("set RAWTRACE_QC_RUN_THERMO_INSTALL_INTEGRATION=1 to download the helper and accept its license"),
)


def test_downloads_installs_accepts_license_and_checks_version(tmp_path: Path) -> None:
    if environment.get_platform() != "win32":
        pytest.skip("ThermoScanHeaderExtractor integration requires Windows.")

    specification = THERMO_HELPER_SPECIFICATION
    data_directory = tmp_path / "app-data"
    initial_status = get_thermo_helper_status(
        data_directory=data_directory,
        specification=specification,
    )
    assert initial_status.state is ThermoHelperState.NOT_INSTALLED

    with urlopen_or_skip(specification.download_url, timeout=60.0):
        pass

    executable = install_thermo_helper(
        data_directory=data_directory,
        specification=specification,
        timeout=60.0,
    )

    assert executable.is_file()
    assert not is_license_accepted(executable, specification.license_marker_name)

    accept_thermo_license(
        data_directory=data_directory,
        specification=specification,
    )

    assert is_license_accepted(executable, specification.license_marker_name)
    assert verify_helper_version(executable, specification.version) == specification.version
