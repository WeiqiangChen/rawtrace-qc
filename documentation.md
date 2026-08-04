# rawtrace-qc Documentation

## Purpose

`rawtrace-qc` is a vendor-neutral Python library for discovering mass-spectrometry raw acquisitions, extracting scan-level traces, validating trace artifacts, and preparing interactive QC reports.

The current discovery implementation supports Bruker timsTOF `.d` directories and Thermo `.raw` files. Thermo extraction is not currently included; discovery only identifies complete Thermo files for later processing.

The package is library-first. Applications such as a command-line tool or GUI should call the public library services rather than implement vendor-specific filesystem or processing logic themselves.

## Features

- [x] Vendor-aware raw-file discovery for Bruker timsTOF `.d` directories and Thermo `.raw` files
- [ ] Bruker scan-trace extraction
- [ ] Thermo scan-trace extraction
- [ ] Scan-trace validation
- [ ] Scan-trace processing
- [ ] HTML report generation
- [ ] Command-line interface
- [ ] Graphical user interface

## Library API

The public library is organized around services that can be used by any application. Applications should provide input directories and options, call the relevant service, and present the returned models to users. Filesystem traversal, vendor recognition, validation, and error handling belong in the library.

The current public service is `rawtrace_qc.discovery.discover`. Later extraction, processing, and reporting services will follow the same pattern and remain independent of any particular application interface.

## File Discovery

Use `discover()` to find valid raw acquisitions below a source directory. By default it examines direct children, uses the built-in Thermo and Bruker validators, requires files to be at least 1 MiB, and requires the relevant recording data to be at least 10 minutes old.

Set `DiscoveryScope.RECURSIVE` to inspect descendants. Recursive traversal does not follow symlinks. A directory ending in `.d` that contains a regular `.tdf` or `.tdf_bin` file is treated as a possible Bruker acquisition and is not traversed further. This prevents files inside an acquisition from being reported as separate acquisitions.

The result contains valid candidates and traversal issues:

- `DiscoveryResult.candidates` contains only complete acquisitions.
- `DiscoveryResult.issues` contains non-fatal problems encountered below the source directory.
- An invalid, inaccessible, symlinked, or non-directory source raises `DiscoveryError`.

Thermo candidates must be non-empty regular files with a case-insensitive `.raw` suffix. Bruker candidates must be directories with a case-insensitive `.d` suffix containing at least one non-empty `.tdf` file and one non-empty, sufficiently old `.tdf_bin` file. Bruker member basenames are arbitrary.

The thresholds and clock are configurable through `DiscoveryOptions`. Additional vendors can be added by registering a validator on `DiscoveryRegistry`. A validator receives the traversed files and directories, the configured thresholds, and the current Unix timestamp. It returns only paths that are valid for that vendor.

### Basic Example

```python
from pathlib import Path

from rawtrace_qc.discovery import DiscoveryOptions, DiscoveryScope, discover

result = discover(
	Path("/data/raw"),
	DiscoveryOptions(scope=DiscoveryScope.RECURSIVE),
)

for candidate in result.candidates:
	print(candidate.vendor, candidate.format, candidate.path)

for issue in result.issues:
	print(f"Could not inspect {issue.path}: {issue.message}")
```

## Application Integration

An application should treat discovery as an input-review step before extraction or reporting:

1. Ask the user for a source directory and discovery scope.
2. Call `discover()` with the selected options.
3. Show valid candidates to the user or pass them to an extractor.
4. Log or display traversal issues without treating them as valid acquisitions.
5. Handle `DiscoveryError` as an input-level failure that requires user action.

The application should not walk raw-file directories itself, inspect vendor-specific member files, or infer validity from filename suffixes. Those rules belong to the discovery service so that the command-line interface, GUI, and other library consumers behave consistently.

## Developer Guide

The project uses `uv` for dependency management and command execution. Install the project and development dependencies with:

```bash
uv sync
```

Run the test suite with:

```bash
uv run pytest
```

Source files use Ruff for linting and formatting. Tests use Ruff for formatting with a 120-character line length; test linting is not enforced.

```bash
uv run ruff check src
uv run ruff format --check src
uv run ruff format --check tests
uv run pyrefly check
```

Source formatting uses the project configuration in `pyproject.toml`. Test formatting uses `tests/ruff.toml`.

## Documentation Maintenance

This document describes behavior that exists in the package. Update it when public APIs, supported formats, configuration, workflows, or known limitations change.