"""Dedicated Thermo helper resolution and caching routines for integration tests."""

from __future__ import annotations

from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest
from rawtrace_qc import environment
from rawtrace_qc.errors import (
    ThermoHelperDownloadError,
    ThermoHelperLicenseError,
    ThermoHelperNotFoundError,
    ThermoHelperVersionError,
)
from rawtrace_qc.thermo import (
    THERMO_HELPER_SPECIFICATION,
    ThermoHelperSpecification,
    ThermoHelperState,
    accept_thermo_license,
    get_thermo_helper_status,
    install_thermo_helper,
)

from tests.support.collection import internet_reachable

_TESTS_ROOT = Path(__file__).resolve().parents[1]
TEST_HELPER_CACHE_DIR = _TESTS_ROOT / ".cache" / "thermo-helper"


def resolve_integration_thermo_helper(
    specification: ThermoHelperSpecification = THERMO_HELPER_SPECIFICATION,
    cache_root: Path = TEST_HELPER_CACHE_DIR,
) -> Path:
    """Resolve a usable ThermoScanHeaderExtractor executable for integration tests.

    Resolution strategy:
    1. Check the real per-user application data directory (read-only). If the
       helper is installed and licensed there, return it.
    2. Fall back to the persistent test cache directory (`tests/.cache/thermo-helper`).
    3. Check status at the test cache. If installed and licensed, return it.
     4. If not installed, install to the test cache. Transient network failures
         trigger a pytest skip; integrity and installation failures propagate.
     5. If installed but unlicensed, accept the cache's license.
     6. Return the ready executable. Version, license, and helper failures remain
         test failures.

    Args:
        specification: Pinned helper specification. Defaults to
            `THERMO_HELPER_SPECIFICATION`.
        cache_root: Root directory for caching the helper across test runs.

    Returns:
        The validated Path to a ready Thermo helper executable.
    """
    if environment.get_platform() != "win32":
        pytest.skip("ThermoScanHeaderExtractor integration requires Windows.")

    real_status = get_thermo_helper_status(specification=specification)
    if real_status.state is ThermoHelperState.READY and real_status.path is not None:
        return real_status.path

    cache_data_dir = cache_root.resolve()
    cache_status = get_thermo_helper_status(
        data_directory=cache_data_dir,
        specification=specification,
    )

    if cache_status.state is ThermoHelperState.INVALID_VERSION:
        raise ThermoHelperVersionError(cache_status.message)
    if cache_status.state is ThermoHelperState.READY and cache_status.path is not None:
        return cache_status.path

    if cache_status.state is ThermoHelperState.NOT_INSTALLED:
        if not internet_reachable():
            pytest.skip(
                f"No usable Thermo helper found at real location and internet is "
                f"unreachable to download to {cache_data_dir}."
            )
        try:
            install_thermo_helper(
                data_directory=cache_data_dir,
                specification=specification,
                timeout=60.0,
            )
        except ThermoHelperDownloadError as error:
            if _is_transient_network_failure(error):
                pytest.skip(f"Network or proxy prevented the Thermo helper download: {error}")
            raise
        cache_status = get_thermo_helper_status(
            data_directory=cache_data_dir,
            specification=specification,
        )
        if cache_status.state is ThermoHelperState.INVALID_VERSION:
            raise ThermoHelperVersionError(cache_status.message)

    if cache_status.state is ThermoHelperState.UNLICENSED:
        if cache_status.path is None:
            raise ThermoHelperLicenseError(cache_status.message)
        accept_thermo_license(
            cache_status.path,
            data_directory=cache_data_dir,
            specification=specification,
        )
        cache_status = get_thermo_helper_status(
            data_directory=cache_data_dir,
            specification=specification,
        )

    if cache_status.state is ThermoHelperState.READY and cache_status.path is not None:
        return cache_status.path

    if cache_status.state is ThermoHelperState.NOT_INSTALLED:
        raise ThermoHelperNotFoundError(cache_status.message)
    if cache_status.state is ThermoHelperState.UNLICENSED:
        raise ThermoHelperLicenseError(cache_status.message)
    if cache_status.state is ThermoHelperState.INVALID_VERSION:
        raise ThermoHelperVersionError(cache_status.message)
    raise RuntimeError(f"Thermo helper is not usable: {cache_status.message}")


def _is_transient_network_failure(error: ThermoHelperDownloadError) -> bool:
    cause = error.__cause__
    while cause is not None:
        if isinstance(cause, HTTPError):
            return cause.code in {403, 407, 408, 429, 502, 503, 504}
        if isinstance(cause, (URLError, TimeoutError, ConnectionError)):
            return True
        cause = cause.__cause__
    return False
