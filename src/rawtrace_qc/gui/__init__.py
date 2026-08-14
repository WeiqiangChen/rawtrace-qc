"""Launch the optional PySide6 rawtrace-qc desktop application."""

from __future__ import annotations


def main() -> int:
    """Start the rawtrace-qc GUI and return its Qt exit code."""
    from rawtrace_qc.gui.app import main as run_gui

    return run_gui()


__all__ = ["main"]
