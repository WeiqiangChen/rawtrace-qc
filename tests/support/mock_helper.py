"""Mock ThermoScanHeaderExtractor helper for unit testing."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from rawtrace_qc.thermo.specification import THERMO_HELPER_SPECIFICATION, THERMO_LICENSE_MARKER_NAME


@dataclass
class MockThermoHelper:
    """Mock runner that mimics the ThermoScanHeaderExtractor contract.

    Supports version queries, license agreement marker creation, and
    configurable failure modes (exit code, empty/garbage stdout, timeouts,
    or execution errors).
    """

    version: str = THERMO_HELPER_SPECIFICATION.version
    exit_code: int = 0
    stdout: str | None = None
    stderr: str = ""
    hang: bool = False
    os_error: OSError | None = None
    commands_run: list[list[str]] = field(default_factory=list)

    def __call__(self, args: Sequence[str | Path], *, timeout: float = 10.0) -> subprocess.CompletedProcess[str]:
        """Execute a simulated helper command."""
        str_args = [str(arg) for arg in args]
        self.commands_run.append(str_args)

        if self.os_error is not None:
            raise self.os_error

        if self.hang:
            raise subprocess.TimeoutExpired(cmd=str_args, timeout=timeout)

        if self.exit_code != 0:
            return subprocess.CompletedProcess(
                args=str_args,
                returncode=self.exit_code,
                stdout=self.stdout or "",
                stderr=self.stderr or f"Process failed with exit code {self.exit_code}.",
            )

        if self.stdout is not None:
            return subprocess.CompletedProcess(args=str_args, returncode=0, stdout=self.stdout, stderr=self.stderr)

        if "--version" in str_args:
            return subprocess.CompletedProcess(args=str_args, returncode=0, stdout=f"{self.version}\n", stderr="")

        if "--agree-to-terms" in str_args:
            exe_path = Path(str_args[0])
            marker = exe_path.parent / THERMO_LICENSE_MARKER_NAME
            marker.write_text("license accepted\n", encoding="utf-8")
            return subprocess.CompletedProcess(args=str_args, returncode=0, stdout="Terms accepted.\n", stderr="")

        return subprocess.CompletedProcess(args=str_args, returncode=0, stdout="", stderr="")


def create_mock_helper_file(
    directory: Path, name: str = THERMO_HELPER_SPECIFICATION.executable_name, *, license_accepted: bool = False
) -> Path:
    """Create a mock helper binary file and optional license marker in a directory.

    Args:
        directory: Destination folder.
        name: Executable filename. Defaults to the pinned helper executable name.
        license_accepted: If True, also creates `.thermo-license-accepted`.
            Defaults to False.

    Returns:
        The created executable path.
    """
    directory.mkdir(parents=True, exist_ok=True)
    executable_path = directory / name
    executable_path.write_bytes(b"MZmock_executable_standin")
    if license_accepted:
        (directory / THERMO_LICENSE_MARKER_NAME).write_text("accepted\n", encoding="utf-8")
    return executable_path


if __name__ == "__main__":
    if "--version" in sys.argv:
        sys.stdout.write(f"{THERMO_HELPER_SPECIFICATION.version}\n")
        sys.exit(0)
    elif "--agree-to-terms" in sys.argv:
        marker = Path(sys.argv[0]).resolve().parent / THERMO_LICENSE_MARKER_NAME
        marker.write_text("accepted\n", encoding="utf-8")
        sys.stdout.write("License terms accepted.\n")
        sys.exit(0)
    else:
        sys.stderr.write("Unknown command\n")
        sys.exit(1)
