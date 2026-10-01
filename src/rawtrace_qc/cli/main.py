"""Main command-line application definition."""

from __future__ import annotations

from collections.abc import Sequence

from cyclopts import App

app = App(name="rawtrace-qc", help="Command-line interface for rawtrace-qc.")
app.command(
    "rawtrace_qc.cli.thermo:thermo_app",
    name="thermo",
    help="Manage ThermoScanHeaderExtractor setup.",
)
app.command(
    "rawtrace_qc.cli.extract:extract",
    name="extract",
    help="Extract traces from Thermo and Bruker acquisitions.",
)


def run(argv: Sequence[str] | None = None) -> int:
    """Run the command-line application.

    Args:
        argv: Optional command arguments. Defaults to the process arguments.

    Returns:
        The selected command's process exit code.
    """
    result = app(argv, result_action="return_value")
    return result if isinstance(result, int) else 0
