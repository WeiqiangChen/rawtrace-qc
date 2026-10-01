"""Command-line interface for rawtrace-qc."""

from __future__ import annotations

import sys
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line application or report missing optional dependencies.

    Args:
        argv: Optional command arguments. Defaults to the process arguments.

    Returns:
        The selected command's process exit code, or `2` when the optional
        Cyclopts dependency is missing.
    """
    try:
        from rawtrace_qc.cli.main import run
    except ModuleNotFoundError as error:
        if error.name != "cyclopts":
            raise
        print(
            "The rawtrace-qc CLI requires the optional 'cli' extra. Install it "
            "with `uv sync --extra cli` or `pip install 'rawtrace-qc[cli]'`.",
            file=sys.stderr,
        )
        return 2
    return run(argv)


__all__ = ["main"]
