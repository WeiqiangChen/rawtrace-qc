"""Main command-line application definition."""

from __future__ import annotations

from collections.abc import Sequence

from cyclopts import App

from rawtrace_qc.cli.thermo import thermo_app

app = App(name="rawtrace-qc", help="Command-line interface for rawtrace-qc.")
app.command(thermo_app)


def run(argv: Sequence[str] | None = None) -> int:
    """Run the command-line application.

    Args:
        argv: Optional command arguments. Defaults to the process arguments.

    Returns:
        The selected command's process exit code.
    """
    result = app(argv, result_action="return_value")
    return result if isinstance(result, int) else 0
