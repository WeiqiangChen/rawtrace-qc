# rawtrace-qc

`rawtrace-qc` is a Python library for extracting mass-spectrometry scan traces and generating interactive HTML QC reports from vendor raw-file formats.

The first implementation targets Bruker timsTOF `.d` directories with a native Python extractor. Thermo `.raw` support is planned through an external helper and is not included in the initial package.

The project is being developed library-first. File discovery, extraction, validated Parquet artifacts, trace processing, and report generation will be implemented and tested before the command-line tool and GUI.

## Development

Install the project and development dependencies with:

```bash
uv sync
```

Run the unit tests, lint checks, formatter check, and type checker with:

```bash
uv run pytest
uv run ruff check src
uv run ruff check tests
uv run ruff format --check src
uv run ruff format --check tests
uv run pyrefly check
```

See `documentation.md` and `implementation-plan.md` for the project design and planned workflows.
