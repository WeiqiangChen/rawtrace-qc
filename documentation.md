# rawtrace-qc Documentation

## Purpose

`rawtrace-qc` is a vendor-neutral Python library for discovering mass-spectrometry raw acquisitions, extracting scan-level traces, validating trace artifacts, and preparing interactive QC reports.

The current implementation supports Bruker timsTOF `.d` discovery and scan-trace extraction, plus Thermo `.raw` discovery. Thermo extraction is deferred because it depends on an external C# helper.

The package is library-first. Applications such as a command-line tool or GUI should call the public library services rather than implement vendor-specific filesystem or processing logic themselves.

## Features

- [x] Vendor-aware raw-file discovery for Bruker timsTOF `.d` directories and Thermo `.raw` files
- [x] Bruker scan-trace extraction
- [ ] Thermo scan-trace extraction
- [x] Scan-trace validation
- [x] Scan-trace processing
    - [ ] FAIMS "combined" mode
    - [ ] Optimize dtype and precision for compact HTML serialization
    - [ ] Process filters requested channels by using `ProcessingOptions`
- [ ] HTML report generation
- [ ] Command-line interface (typer or **cyclopts**)
- [ ] Graphical user interface (pyside6)

## Library API

The public library is organized around services that can be used by any application. Applications should provide input directories and options, call the relevant service, and present the returned models to users. Filesystem traversal, vendor recognition, validation, and error handling belong in the library.

The public services currently include `rawtrace_qc.discovery.discover`, `rawtrace_qc.extractors.BrukerExtractor`, and the trace artifact functions in `rawtrace_qc.traces`. Later processing and reporting services will follow the same pattern and remain independent of any particular application interface.

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

## Scan-Trace Extraction

`BrukerExtractor.extract()` reads native frame metadata from `analysis.tdf`, including `Frames.SummedIntensities` for total ion current and `Frames.MaxIntensity` for base-peak intensity when those optional columns are available. It writes schema-v1 Snappy Parquet artifacts using the naming convention `<run-name>.ms1-trace.parquet` and `<run-name>.msn-trace.parquet`.

Both `select_ms1` and `select_msn` default to `True`. This writes every available level: an MS1 artifact is written when MS1 rows exist, and an MSn artifact is written only when MSn rows exist. Selecting only one level writes only that level. Selecting a level that does not exist raises an error, except that an all-level request omits unavailable levels. When both flags are `False`, the input is structurally checked and no output is created.

Bruker MSn rows have `row_granularity` set to `frame-aggregate`. A frame can contain multiple precursor isolation events, so these rows must not be interpreted as individual precursor spectra.

### Basic Extraction Example

```python
from pathlib import Path

from rawtrace_qc.extractors import BrukerExtractor
from rawtrace_qc.traces import load_trace

result = BrukerExtractor().extract(
	Path("/data/raw/sample.d"),
	output_directory=Path("/data/traces"),
	precision_mode="high",
)

if result.ms1_path is not None:
	ms1 = load_trace(result.ms1_path)
	print(ms1.table.num_rows, ms1.metadata["vendor"])

if result.msn_path is not None:
	msn = load_trace(result.msn_path)
	print(msn.metadata["row_granularity"])
```

The extractor overwrites existing artifacts with the same destination path. It currently emits `scan_id`, `retention_time_sec`, `ms_level`, and the available native `total_ion_current` and `base_peak_intensity` columns. The test SQLite fixture retains additional frame fields such as `AccumulationTime` for future extraction work, but `injection_time_ms` is not emitted yet.

Bruker extraction records `GlobalMetadata.AcquisitionDateTime` as the required `acquisition_start_time` metadata field, normalized to an ISO-8601 UTC timestamp and shared by the MS1 and MSn artifacts.

## Scan-Trace Import and Validation

`load_trace(path)` reads a Parquet artifact into an Arrow table and validates its required columns, metadata, MS-level contents, and Snappy compression before returning a `TraceArtifact`. The same table and metadata contract is available through `validate_trace(table, metadata)` for callers that construct artifacts in memory. Arrow tables are immutable, so transformations such as filtering, casting, adding columns, and dropping columns return new tables. Later processing code can keep using Arrow or convert to pandas only when a pandas-specific operation or report library requires it.

Validation is strict by default and rejects columns that are not implemented by this package. Use `load_trace(path, strict=False)` when consuming artifacts that contain contract-defined future columns or additional producer columns. Known future columns are still type-checked in non-strict mode; unknown columns are ignored.

The artifact contract requires `scan_id`, `retention_time_sec`, and `ms_level`. Optional columns may be omitted when unavailable, while null values in present optional columns represent row-level extraction failure. Required columns cannot contain null values. A `faims_cv` column must contain either only null values or a finite numeric value for every row.

## Scan-Trace Processing

`process_traces()` prepares one or more loaded `TraceArtifact` instances for report generation without depending on Plotly, pandas, or another report library. It returns a tuple of immutable `ProcessedTable` objects. Each object contains a report-ready Arrow table and a `ProcessedTableMetadata` dataclass.

The default processing options select MS1 and MS2, split tables by FAIMS compensation voltage when `faims_cv` contains values, and convert retention time from seconds to minutes. An MSn artifact containing several levels is therefore split into one processed table per selected MS level and FAIMS partition. Global FAIMS mode is ignored for tables without FAIMS values. `FaimsProcessingMode.COMBINED` is reserved for a future implementation and raises `NotImplementedError` for FAIMS-bearing tables. Set `minimum_faims_percentage` to a value from 0 to 100 to omit FAIMS partitions containing fewer than that percentage of rows in their selected MS-level table.

Processed tables contain `retention_time_min` and the available `total_ion_current` and `base_peak_intensity` columns. The retention-time unit is recorded as `time_unit="min"`. `scan_id`, `ms_level`, and `faims_cv` are removed from the processed table because they are represented in the table metadata. Source fields such as vendor, source path, generator, extraction time, acquisition start time, precision, and row granularity are copied into `ProcessedTableMetadata`.

Labels initially equal the raw-file name. Use `relabel_tables()` to create new processed-table instances with shortened or otherwise customized display labels without mutating the original results. Plotly figures, colors, line styles, channel controls, and HTML serialization belong to the later report layer.

### Processing Example

```python
from pathlib import Path

from rawtrace_qc.processing import process_traces, relabel_tables
from rawtrace_qc.traces import load_trace

artifacts = [
	load_trace(Path("/data/traces/sample.ms1-trace.parquet")),
	load_trace(Path("/data/traces/sample.msn-trace.parquet")),
]
processed = process_traces(artifacts)
processed = relabel_tables(processed, [table.metadata.rawfile_name for table in processed])

for item in processed:
	print(item.metadata.label, item.metadata.ms_level)
	print(item.table.column_names)
```

The current processor expects valid schema-v1 artifacts; `validate_trace()` owns source-contract checks before partitioning begins. Precision reduction for compact HTML serialization is reserved for a later implementation because its exact representation depends on the report serializer.

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