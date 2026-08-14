# rawtrace-qc

`rawtrace-qc` is a Python library for extracting mass-spectrometry scan traces and generating interactive HTML QC reports from vendor raw-file formats.

The first implementation targets Bruker timsTOF `.d` directories with a native Python extractor. Thermo `.raw` support is planned through an external helper and is not included in the initial package.

The project is being developed library-first. File discovery, extraction, validated Parquet artifacts, trace processing, report generation, and the optional GUI are implemented as clients of the same service layers.

## Development

Install the project and development dependencies with:

```bash
uv sync
```

Run the unit tests, source lint and formatter checks, test formatting check, and type checker with:

```bash
uv run pytest
uv run ruff check src
uv run ruff format --check src
uv run ruff format --check tests
uv run pyrefly check
```

Install the optional PySide6 desktop GUI with:

```bash
uv sync --extra gui
rawtrace-qc-gui
```

Ruff formatting is applied to tests with the separate 120-character test configuration. Test linting is intentionally not enforced.

See `documentation.md` and `implementation-plan.md` for the project design and planned workflows.
