"""Collection hooks and item tagging for test folders and markers."""

from __future__ import annotations

import socket
from collections.abc import Sequence
from pathlib import Path

import pytest

_TESTS_ROOT = Path(__file__).resolve().parent.parent


def internet_reachable(host: str = "github.com", port: int = 443, timeout: float = 2.0) -> bool:
    """Check if internet access to a given host is available.

    Args:
        host: Hostname to probe. Defaults to "github.com".
        port: Port to connect to. Defaults to 443.
        timeout: Socket timeout in seconds. Defaults to 2.0.

    Returns:
        True if the connection succeeded, False otherwise.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def tag_test_items(
    items: Sequence[pytest.Item],
    *,
    tests_root: Path | None = None,
    reachable: bool | None = None,
) -> None:
    """Tag collected test items with folder-derived markers and handle offline skipping.

    Items located under `unit/`, `network/`, and `integration/` receive the corresponding
    marker. Tests in `network/` are additionally skipped if internet connectivity is absent.

    Args:
        items: Pytest test items collected for the session.
        tests_root: Optional root path for test directories. Defaults to the resolved tests folder.
        reachable: Optional internet connectivity flag. If None (default), checked dynamically.
    """
    root = (tests_root or _TESTS_ROOT).resolve()
    tier_dirs = {
        "unit": root / "unit",
        "network": root / "network",
        "integration": root / "integration",
    }

    classified: list[tuple[pytest.Item, str | None]] = []
    has_network_items = False

    for item in items:
        item_path = getattr(item, "path", None)
        if item_path is None:
            item_path = Path(item.fspath)
        resolved_path = item_path.resolve()

        matched_tier: str | None = None
        for tier, tier_dir in tier_dirs.items():
            if _is_relative_to(resolved_path, tier_dir):
                matched_tier = tier
                break

        if matched_tier == "network":
            has_network_items = True

        classified.append((item, matched_tier))

    is_offline = not (internet_reachable() if reachable is None else reachable) if has_network_items else False
    skip_network = pytest.mark.skip(reason="no internet connection to GitHub")

    for item, tier in classified:
        if tier == "unit":
            item.add_marker(pytest.mark.unit)
        elif tier == "network":
            item.add_marker(pytest.mark.network)
            if is_offline:
                item.add_marker(skip_network)
        elif tier == "integration":
            item.add_marker(pytest.mark.integration)


def _is_relative_to(path: Path, directory: Path) -> bool:
    try:
        return path.is_relative_to(directory)
    except (ValueError, OSError):
        return False
