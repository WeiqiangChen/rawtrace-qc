"""Implement generic traversal and vendor-aware candidate discovery."""

from __future__ import annotations

import glob
import os
import stat
from collections import deque
from collections.abc import Iterable, Iterator
from pathlib import Path

from rawtrace_qc.discovery.models import (
    DiscoveryCandidate,
    DiscoveryIssue,
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
from rawtrace_qc.errors import ConfigurationError, DiscoveryError


def discover_inputs(
    inputs: Iterable[str | os.PathLike[str]],
    options: DiscoveryOptions | None = None,
    registry: DiscoveryRegistry | None = None,
) -> DiscoveryResult:
    """Resolve paths and glob patterns, then discover supported acquisitions.

    Each input is expanded independently of the discovery scope. Glob patterns
    support `*`, `?`, character classes, and recursive `**`. Each matching path
    is first validated as a complete acquisition; paths that are not
    acquisitions are scanned as directories using the selected options.
    Candidates found through multiple inputs are included once, and all
    non-fatal input-resolution and traversal issues are returned.

    Examples:
        ```python
        from rawtrace_qc.discovery import DiscoveryOptions, DiscoveryScope
        from rawtrace_qc.discovery import discover_inputs

        result = discover_inputs(
            ["/data/**/*.raw", "/data/run.d"],
            DiscoveryOptions(scope=DiscoveryScope.RECURSIVE),
        )
        ```

    Args:
        inputs: Acquisition paths, directories, or glob patterns to resolve.
        options: Discovery configuration. If None (default), uses direct
            discovery, all built-in vendors, default thresholds, and the system
            clock.
        registry: Validator registry. If None (default), uses Bruker and Thermo.

    Returns:
        Deduplicated valid candidates and non-fatal input or traversal issues.

    Raises:
        ConfigurationError: If no input paths are supplied.
    """
    input_paths = tuple(Path(path).expanduser().absolute() for path in inputs)
    if not input_paths:
        raise ConfigurationError("At least one input path is required.")

    selected = options or DiscoveryOptions()
    candidates: list[DiscoveryCandidate] = []
    issues: list[DiscoveryIssue] = []
    seen: set[str] = set()

    for input_path in input_paths:
        resolved_paths = resolve_input_path_pattern(input_path)
        if not resolved_paths:
            if glob.has_magic(os.fspath(input_path)):
                issues.append(
                    DiscoveryIssue(
                        input_path,
                        f"No paths matched input pattern {input_path!r}.",
                        code="pattern_no_matches",
                    )
                )
            else:
                issues.append(
                    DiscoveryIssue(
                        input_path,
                        f"Input path {input_path!r} does not exist.",
                        code="path_not_found",
                    )
                )
            continue

        for resolved_path in resolved_paths:
            candidate = validate_path(resolved_path, selected, registry)
            if candidate is not None:
                input_candidates = (candidate,)
            else:
                try:
                    discovery_result = discover(resolved_path, selected, registry)
                except DiscoveryError as error:
                    issues.append(
                        DiscoveryIssue(
                            resolved_path, str(error), code="input_resolution"
                        )
                    )
                    continue

                issues.extend(discovery_result.issues)
                if not discovery_result.candidates:
                    issues.append(
                        DiscoveryIssue(
                            resolved_path,
                            "No supported complete acquisitions were found.",
                            code="no_candidates",
                        )
                    )
                input_candidates = discovery_result.candidates

            for input_candidate in input_candidates:
                key = _path_key(input_candidate.path)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(input_candidate)

    return DiscoveryResult(tuple(candidates), tuple(issues))


def resolve_input_path_pattern(input_path: str | os.PathLike[str]) -> list[Path]:
    """Return existing paths matched by a literal path or glob pattern.

    Glob patterns support `*`, `?`, character classes, and recursive `**`.
    This function resolves filesystem paths only and does not validate
    acquisition formats.

    Args:
        input_path: File path, directory path, or glob pattern to resolve.

    Returns:
        Matching existing paths as absolute `Path` objects, or an empty list
        when the path does not exist or the pattern has no matches.
    """
    normalized_path = Path(input_path).expanduser().absolute()
    pattern = os.fspath(normalized_path)
    if not glob.has_magic(pattern):
        return [normalized_path] if os.path.lexists(normalized_path) else []

    matches: list[Path] = []
    seen: set[str] = set()
    for match in glob.iglob(pattern, recursive=True):
        path = Path(match).absolute()
        key = _path_key(path)
        if key in seen or not os.path.lexists(path):
            continue
        seen.add(key)
        matches.append(path)
    return sorted(matches, key=_path_key)


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

    candidates: list[DiscoveryCandidate] = []
    seen: set[str] = set()
    for candidate in _validated_candidates(tree, selected, registry):
        key = _path_key(candidate.path)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(candidate)

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
    normalized_path = Path(path).expanduser().absolute()
    try:
        metadata = os.lstat(normalized_path)
    except OSError:
        return None
    if stat.S_ISLNK(metadata.st_mode):
        return None

    if stat.S_ISREG(metadata.st_mode):
        tree = TraversalTree(files=(normalized_path,))
    elif stat.S_ISDIR(metadata.st_mode):
        tree = TraversalTree(directories=(normalized_path,))
    else:
        return None

    path_key = _path_key(normalized_path)
    for candidate in _validated_candidates(tree, selected, registry):
        if _path_key(candidate.path) == path_key:
            return DiscoveryCandidate(
                normalized_path, candidate.vendor, candidate.format
            )
    return None


def _validated_candidates(
    tree: TraversalTree,
    options: DiscoveryOptions,
    registry: DiscoveryRegistry | None,
) -> Iterator[DiscoveryCandidate]:
    """Yield candidates returned by the selected validators.

    Args:
        tree: Files and directories supplied to each validator.
        options: Vendor filter and validation thresholds.
        registry: Validator registry, or `None` for the built-in registry.

    Yields:
        Candidates accepted by the selected validators.
    """
    active_registry = registry or _default_registry()
    now = options.clock()
    for vendor, format, validator in active_registry:
        if options.vendors is not None and vendor not in options.vendors:
            continue
        for path in validator(
            tree, options.min_size_bytes, options.min_age_seconds, now
        ):
            yield DiscoveryCandidate(path, vendor, format)


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
