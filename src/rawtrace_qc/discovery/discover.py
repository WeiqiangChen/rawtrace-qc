"""Implement generic traversal and vendor-aware candidate discovery."""

from __future__ import annotations

import os
import stat
from collections import deque
from pathlib import Path

from rawtrace_qc.discovery.models import (
    DiscoveryCandidate,
    DiscoveryOptions,
    DiscoveryResult,
    DiscoveryScope,
    TraversalIssue,
    TraversalTree,
)
from rawtrace_qc.discovery.policies import (
    FileFormat,
    Vendor,
    validate_bruker,
    validate_thermo,
)
from rawtrace_qc.discovery.registry import DiscoveryRegistry
from rawtrace_qc.errors import DiscoveryError


def discover(
    source: Path,
    options: DiscoveryOptions | None = None,
    registry: DiscoveryRegistry | None = None,
) -> DiscoveryResult:
    """Discover valid raw acquisitions below a directory.

    Symlinks are never followed. In recursive mode, a `.d` directory
    containing a case-insensitive `.tdf` or `.tdf_bin` file is recorded but
    pruned so its contents are not treated as separate acquisitions. An
    inaccessible descendant is returned as a traversal issue; an inaccessible,
    missing, symlinked, or non-directory source raises `DiscoveryError`.

    Args:
        source: Directory whose children or descendants should be examined.
        options: Discovery configuration. If None (default), uses direct
            discovery, all built-in vendors, default thresholds, and the system
            clock.
        registry: Validator registry. If None (default), uses Bruker and Thermo.

    Returns:
        Valid candidates in deterministic path order and non-fatal traversal
        issues encountered below the source directory.

    Raises:
        DiscoveryError: If the source cannot be used as a real directory.
    """
    selected = options or DiscoveryOptions()
    source = Path(source)
    _validate_source(source)
    tree = _traverse(source, selected.scope)
    active_registry = registry or _default_registry()
    now = selected.clock()

    candidates: list[DiscoveryCandidate] = []
    seen: set[str] = set()
    for vendor, format, validator in active_registry:
        if selected.vendors is not None and vendor not in selected.vendors:
            continue
        for path in validator(
            tree, selected.min_size_bytes, selected.min_age_seconds, now
        ):
            key = _path_key(path)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(DiscoveryCandidate(path, vendor, format))

    candidates.sort(
        key=lambda candidate: (
            _path_key(candidate.path),
            candidate.vendor,
            candidate.format,
        )
    )
    return DiscoveryResult(tuple(candidates), tree.issues)


def validate_path(
    path: Path,
    options: DiscoveryOptions | None = None,
    registry: DiscoveryRegistry | None = None,
) -> DiscoveryCandidate | None:
    """Validate one possible acquisition path.

    This is the single-path counterpart to `discover()` for workflows such as
    drag and drop or file-dialog selection. Symlinks, unsupported path types,
    and paths rejected by every registered validator return `None`.

    Args:
        path: File or directory to validate.
        options: Discovery configuration. If None (default), uses the default
            thresholds and the system clock.
        registry: Validator registry. If None (default), uses Bruker and
            Thermo validators.

    Returns:
        A valid acquisition candidate, or `None` when the path is not a
        supported complete acquisition.
    """
    selected = options or DiscoveryOptions()
    resolved_path = Path(path).expanduser().resolve()
    try:
        metadata = os.lstat(resolved_path)
    except OSError:
        return None
    if stat.S_ISLNK(metadata.st_mode):
        return None

    if stat.S_ISREG(metadata.st_mode):
        tree = TraversalTree(files=(resolved_path,))
    elif stat.S_ISDIR(metadata.st_mode):
        tree = TraversalTree(directories=(resolved_path,))
    else:
        return None

    active_registry = registry or _default_registry()
    now = selected.clock()
    path_key = _path_key(resolved_path)
    for vendor, format, validator in active_registry:
        if selected.vendors is not None and vendor not in selected.vendors:
            continue
        valid_paths = validator(
            tree, selected.min_size_bytes, selected.min_age_seconds, now
        )
        if any(_path_key(candidate) == path_key for candidate in valid_paths):
            return DiscoveryCandidate(resolved_path, vendor, format)
    return None


def _default_registry() -> DiscoveryRegistry:
    registry = DiscoveryRegistry()
    registry.register(Vendor.THERMO, FileFormat.RAW, validate_thermo)
    registry.register(Vendor.BRUKER, FileFormat.D, validate_bruker)
    return registry


def _path_key(path: Path) -> str:
    return os.path.normcase(os.path.abspath(path))


def _has_bruker_marker(path: Path) -> tuple[bool, TraversalIssue | None]:
    try:
        with os.scandir(path) as scan:
            for member in scan:
                if member.is_symlink() or not member.is_file(follow_symlinks=False):
                    continue
                suffix = member.name.casefold()
                if suffix.endswith(".tdf") or suffix.endswith(".tdf_bin"):
                    return True, None
    except OSError as error:
        return False, TraversalIssue(
            path,
            "inaccessible",
            f"Cannot inspect {path!r} while deciding whether to prune it: "
            f"{error.strerror or error}.",
        )
    return False, None


def _traverse(source: Path, scope: DiscoveryScope) -> TraversalTree:
    files: list[Path] = []
    directories: list[Path] = []
    issues: list[TraversalIssue] = []
    pending = deque([source])
    visited = {_path_key(source)}

    while pending:
        current = pending.popleft()
        try:
            with os.scandir(current) as scan:
                entries = sorted(tuple(scan), key=lambda entry: entry.name.casefold())
        except OSError as error:
            if current == source:
                raise DiscoveryError(
                    f"Cannot access discovery source {source!r}: "
                    f"{error.strerror or error}."
                ) from error
            issues.append(
                TraversalIssue(
                    current,
                    "inaccessible",
                    f"Cannot access directory {current!r}: {error.strerror or error}.",
                )
            )
            continue

        for entry in entries:
            entry_path = Path(entry.path)
            try:
                if entry.is_symlink():
                    continue
                if entry.is_file(follow_symlinks=False):
                    files.append(entry_path)
                    continue
                if not entry.is_dir(follow_symlinks=False):
                    continue
                directories.append(entry_path)
                if scope is DiscoveryScope.DIRECT:
                    continue
                if entry.name.casefold().endswith(".d"):
                    has_marker, issue = _has_bruker_marker(entry_path)
                    if issue is not None:
                        issues.append(issue)
                    if has_marker or issue is not None:
                        continue
                if _path_key(entry_path) not in visited:
                    visited.add(_path_key(entry_path))
                    pending.append(entry_path)
            except OSError as error:
                issues.append(
                    TraversalIssue(
                        entry_path,
                        "inaccessible",
                        f"Cannot inspect filesystem entry {entry_path!r}: "
                        f"{error.strerror or error}.",
                    )
                )
    return TraversalTree(tuple(files), tuple(directories), tuple(issues))


def _validate_source(source: Path) -> None:
    try:
        metadata = os.lstat(source)
    except OSError as error:
        raise DiscoveryError(
            f"Cannot access discovery source {source!r}: {error.strerror or error}."
        ) from error
    if stat.S_ISLNK(metadata.st_mode):
        raise DiscoveryError(
            f"Discovery source {source!r} is a symlink; provide a real directory."
        )
    if not stat.S_ISDIR(metadata.st_mode):
        raise DiscoveryError(f"Discovery source {source!r} is not a directory.")
