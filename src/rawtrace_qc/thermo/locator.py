"""Locating and status reporting for the ThermoScanHeaderExtractor helper."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from rawtrace_qc import environment
from rawtrace_qc.errors import (
    ThermoHelperLicenseError,
    ThermoHelperNotFoundError,
    ThermoHelperVersionError,
    UnsupportedPlatformError,
)
from rawtrace_qc.thermo.specification import (
    THERMO_HELPER_SPECIFICATION,
    THERMO_LICENSE_MARKER_NAME,
    ThermoHelperSpecification,
)


class ThermoHelperState(StrEnum):
    """Represent the readiness state of ThermoScanHeaderExtractor."""

    READY = "ready"
    UNLICENSED = "unlicensed"
    INVALID_VERSION = "invalid_version"
    NOT_INSTALLED = "not_installed"
    UNSUPPORTED_PLATFORM = "unsupported_platform"


@dataclass(frozen=True, slots=True)
class ThermoHelperStatus:
    """Describe the installation, version, and license state of the helper."""

    state: ThermoHelperState
    path: Path | None
    version: str | None
    license_accepted: bool
    message: str
    expected_version: str = THERMO_HELPER_SPECIFICATION.version

    @property
    def is_ready(self) -> bool:
        """Return True if the helper is installed, verified, and licensed."""
        return self.state is ThermoHelperState.READY


def locate_thermo_helper(
    explicit_path: Path | str | None = None,
    *,
    data_directory: Path | str | None = None,
    specification: ThermoHelperSpecification = THERMO_HELPER_SPECIFICATION,
) -> Path:
    """Locate and return a usable ThermoScanHeaderExtractor executable.

    Checks that the current platform is Windows, resolves the executable path
    by priority, verifies that the helper is installed, checks that its version
    matches the pinned specification, and verifies that the license agreement
    has been accepted.

    Args:
        explicit_path: Optional explicit executable or directory path. Defaults
            to None.
        data_directory: Data directory root. If None (default), uses the
            platform default user data directory.
        specification: Release specification. Defaults to
            `THERMO_HELPER_SPECIFICATION`.
    Returns:
        The validated Path to the usable ThermoScanHeaderExtractor executable.

    Raises:
        UnsupportedPlatformError: If the platform is not Windows (`"win32"`).
        ThermoHelperNotFoundError: If no helper executable is found.
        ThermoHelperVersionError: If the helper version is wrong or unreadable.
        ThermoHelperLicenseError: If the Thermo license agreement has not been
            accepted.

    Examples:
        ```python
        from rawtrace_qc.thermo import locate_thermo_helper

        executable = locate_thermo_helper()
        print(f"Using helper at: {executable}")
        ```
    """
    status = get_thermo_helper_status(
        explicit_path,
        data_directory=data_directory,
        specification=specification,
    )

    if status.state is ThermoHelperState.NOT_INSTALLED:
        raise ThermoHelperNotFoundError(status.message)
    if status.state is ThermoHelperState.INVALID_VERSION:
        raise ThermoHelperVersionError(status.message)
    if status.state is ThermoHelperState.UNLICENSED:
        raise ThermoHelperLicenseError(status.message)
    if status.state is ThermoHelperState.UNSUPPORTED_PLATFORM:
        raise UnsupportedPlatformError(status.message)

    if status.path is None:
        raise ThermoHelperNotFoundError(status.message)

    return status.path


def get_thermo_helper_status(
    explicit_path: Path | str | None = None,
    *,
    data_directory: Path | str | None = None,
    specification: ThermoHelperSpecification = THERMO_HELPER_SPECIFICATION,
) -> ThermoHelperStatus:
    """Inspect the status of ThermoScanHeaderExtractor without side effects.

    Checks what is present, what version it is, and whether the license has
    been accepted. If the helper is not installed, no process is executed.

    Args:
        explicit_path: Optional explicit executable or directory path. Defaults
            to None.
        data_directory: Data directory root. If None (default), uses the
            platform default user data directory.
        specification: Release specification. Defaults to
            `THERMO_HELPER_SPECIFICATION`.
    Returns:
        A `ThermoHelperStatus` instance describing the helper state.
    """
    current_platform = environment.get_platform()
    if current_platform != "win32":
        return ThermoHelperStatus(
            state=ThermoHelperState.UNSUPPORTED_PLATFORM,
            path=None,
            version=None,
            license_accepted=False,
            message=(
                f"ThermoScanHeaderExtractor requires Windows, but current platform is "
                f"{current_platform!r}. Thermo .raw extraction is only "
                "supported on Windows."
            ),
            expected_version=specification.version,
        )

    candidate = find_thermo_helper_path(
        explicit_path,
        data_directory=data_directory,
        specification=specification,
    )

    if candidate is None:
        searched_paths: list[str] = []
        if explicit_path is not None:
            searched_paths.append(str(Path(explicit_path).expanduser()))
        managed_path = (
            environment.helper_tool_directory(
                specification.tool_name,
                specification.version,
                data_directory=data_directory,
            )
            / specification.executable_name
        )
        searched_paths.append(str(managed_path))
        searched_summary = ", ".join(searched_paths)

        return ThermoHelperStatus(
            state=ThermoHelperState.NOT_INSTALLED,
            path=None,
            version=None,
            license_accepted=False,
            message=(
                f"ThermoScanHeaderExtractor executable was not found. "
                f"Checked: {searched_summary}. Please install "
                f"ThermoScanHeaderExtractor v{specification.version} or "
                "supply a valid executable path."
            ),
            expected_version=specification.version,
        )

    license_accepted = is_license_accepted(candidate, specification.license_marker_name)

    try:
        reported_version = query_helper_version(candidate)
    except ThermoHelperVersionError as error:
        return ThermoHelperStatus(
            state=ThermoHelperState.INVALID_VERSION,
            path=candidate,
            version=None,
            license_accepted=license_accepted,
            message=(
                f"ThermoScanHeaderExtractor at {candidate} has an unreadable "
                f"version: {error}"
            ),
            expected_version=specification.version,
        )

    if reported_version != specification.version:
        return ThermoHelperStatus(
            state=ThermoHelperState.INVALID_VERSION,
            path=candidate,
            version=reported_version,
            license_accepted=license_accepted,
            message=(
                f"ThermoScanHeaderExtractor at {candidate} reported version "
                f"{reported_version!r}, but expected {specification.version!r}. "
                f"Please install version {specification.version!r}."
            ),
            expected_version=specification.version,
        )

    if not license_accepted:
        return ThermoHelperStatus(
            state=ThermoHelperState.UNLICENSED,
            path=candidate,
            version=reported_version,
            license_accepted=False,
            message=(
                f"ThermoScanHeaderExtractor at {candidate} is installed "
                f"(version {reported_version}), but the Thermo license "
                "agreement has not been accepted. Run "
                f"'{candidate.name} --agree-to-terms' to accept the license "
                "before use."
            ),
            expected_version=specification.version,
        )

    return ThermoHelperStatus(
        state=ThermoHelperState.READY,
        path=candidate,
        version=reported_version,
        license_accepted=True,
        message=(
            f"ThermoScanHeaderExtractor v{reported_version} at {candidate} is ready."
        ),
        expected_version=specification.version,
    )


def find_thermo_helper_path(
    explicit_path: Path | str | None = None,
    *,
    data_directory: Path | str | None = None,
    specification: ThermoHelperSpecification = THERMO_HELPER_SPECIFICATION,
) -> Path | None:
    """Resolve the candidate ThermoScanHeaderExtractor path by priority.

    Resolution order:
    1. An explicitly supplied path, if provided and existing on disk.
    2. The managed install path in the user data directory for the pinned version.

    Does not execute the helper and returns None if neither candidate exists.

    Args:
        explicit_path: Optional explicit executable or directory path. Defaults
            to None.
        data_directory: Data directory root. If None (default), uses the
            platform default user data directory.
        specification: Release specification. Defaults to
            `THERMO_HELPER_SPECIFICATION`.

    Returns:
        The resolved executable path if a file exists, or None if neither
        location exists.
    """
    if explicit_path is not None:
        explicit = Path(explicit_path).expanduser().resolve()
        if explicit.is_file():
            return explicit
        if explicit.is_dir():
            candidate = explicit / specification.executable_name
            if candidate.is_file():
                return candidate.resolve()

    managed_path = (
        environment.helper_tool_directory(
            specification.tool_name,
            specification.version,
            data_directory=data_directory,
        )
        / specification.executable_name
    ).resolve()
    if managed_path.is_file():
        return managed_path

    return None


def verify_helper_version(
    executable_path: Path,
    expected_version: str = THERMO_HELPER_SPECIFICATION.version,
    *,
    timeout: float = 10.0,
) -> str:
    """Verify that the helper reports the expected version.

    Args:
        executable_path: Path to the ThermoScanHeaderExtractor executable.
        expected_version: Expected release version. Defaults to the pinned
            version in `THERMO_HELPER_SPECIFICATION`.
        timeout: Maximum time to wait in seconds. Defaults to 10.0.

    Returns:
        The verified version string.

    Raises:
        ThermoHelperVersionError: If the reported version does not match
            `expected_version` or cannot be read.
    """
    reported = query_helper_version(executable_path, timeout=timeout)
    if reported != expected_version:
        raise ThermoHelperVersionError(
            f"ThermoScanHeaderExtractor at {executable_path} reported version "
            f"{reported!r}, but expected {expected_version!r}. Please install "
            f"version {expected_version!r}."
        )
    return reported


def query_helper_version(
    executable_path: Path,
    *,
    timeout: float = 10.0,
) -> str:
    """Query the version reported by ThermoScanHeaderExtractor.

    Executes the helper with `--version` and returns the trimmed first line of output.

    Args:
        executable_path: Path to the ThermoScanHeaderExtractor executable.
        timeout: Maximum time to wait in seconds. Defaults to 10.0.

    Returns:
        The version string reported by the tool.

    Raises:
        ThermoHelperVersionError: If the tool fails to run, exits with non-zero
            status, times out, or returns an unreadable version.
    """
    try:
        result = execute_helper_process([executable_path, "--version"], timeout=timeout)
    except subprocess.TimeoutExpired as error:
        raise ThermoHelperVersionError(
            f"ThermoScanHeaderExtractor at {executable_path} timed out after "
            f"{timeout} seconds when querying version."
        ) from error
    except OSError as error:
        raise ThermoHelperVersionError(
            f"Failed to execute ThermoScanHeaderExtractor at "
            f"{executable_path}: {error}."
        ) from error

    if result.returncode != 0:
        stderr_sample = result.stderr.strip()
        detail = f": {stderr_sample}" if stderr_sample else ""
        raise ThermoHelperVersionError(
            f"ThermoScanHeaderExtractor at {executable_path} failed with exit "
            f"code {result.returncode}{detail}."
        )

    output = result.stdout.strip()
    if not output:
        raise ThermoHelperVersionError(
            f"ThermoScanHeaderExtractor at {executable_path} returned empty "
            "version output."
        )

    version_line = next(
        (line.strip() for line in output.splitlines() if line.strip()), ""
    )
    if not version_line:
        raise ThermoHelperVersionError(
            f"ThermoScanHeaderExtractor at {executable_path} returned "
            f"unreadable version output {output!r}."
        )
    return version_line


def is_license_accepted(
    executable_path: Path,
    marker_name: str = THERMO_LICENSE_MARKER_NAME,
) -> bool:
    """Return whether the Thermo license agreement has been accepted.

    Checks for the presence of the license marker file beside the helper
    executable.

    Args:
        executable_path: Path to the ThermoScanHeaderExtractor executable.
        marker_name: Marker filename. Defaults to
            `THERMO_LICENSE_MARKER_NAME`.

    Returns:
        True if the license marker file exists, False otherwise.
    """
    marker = executable_path.parent / marker_name
    return marker.is_file()


def execute_helper_process(
    args: Sequence[str | Path],
    *,
    timeout: float = 10.0,
) -> subprocess.CompletedProcess[str]:
    """Execute a low-level Thermo helper command.

    Args:
        args: Command arguments starting with the executable path.
        timeout: Maximum execution time in seconds. Defaults to 10.0.

    Returns:
        The completed process result with captured standard output and error.

    Raises:
        OSError: If the process cannot be started or executable is missing.
        subprocess.TimeoutExpired: If the process exceeds the timeout.
    """
    str_args = [str(arg) for arg in args]
    return subprocess.run(
        str_args,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
