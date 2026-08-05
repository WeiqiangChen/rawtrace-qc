from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from rawtrace_qc.errors import ArtifactValidationError
from rawtrace_qc.traces import load_trace, validate_trace, write_trace


def _table() -> pa.Table:
    return pa.table(
        {
            "scan_id": pa.array([1, 2], type=pa.int32()),
            "retention_time_sec": pa.array([1.0, 2.0], type=pa.float32()),
            "ms_level": pa.array([1, 1], type=pa.int8()),
            "total_ion_current": pa.array([10.0, 20.0], type=pa.float32()),
        }
    )


def _metadata(ms_level_file: str = "ms1") -> dict[bytes, bytes]:
    return {
        key.encode(): value.encode()
        for key, value in {
            "schema_version": "1",
            "generator": "test/1.0",
            "vendor": "bruker",
            "ms_level_file": ms_level_file,
            "precision_mode": "low",
            "row_granularity": "spectrum",
            "source_path": "C:/sample.d",
            "extracted_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }.items()
    }


class TestScanTraceWriting:
    def test_write_and_load_round_trip_returns_arrow_table_and_metadata(self, tmp_path: Path) -> None:
        path = write_trace(
            _table(),
            tmp_path / "sample.ms1-trace.parquet",
            vendor="bruker",
            ms_level_file="ms1",
            precision_mode="low",
            row_granularity="spectrum",
            source_path=tmp_path / "sample.d",
            extracted_at="2026-08-04T12:00:00Z",
            generator="test/1.0",
        )

        artifact = load_trace(path)

        assert artifact.table.equals(_table())
        assert artifact.metadata["vendor"] == "bruker"
        assert pq.ParquetFile(path).metadata.row_group(0).column(0).compression == "SNAPPY"


class TestScanTraceValidation:
    def test_public_validator_accepts_valid_trace(self) -> None:
        metadata = {key.decode(): value.decode() for key, value in _metadata().items()}

        validate_trace(_table(), metadata)

    def test_load_accepts_numeric_faims_column(self, tmp_path: Path) -> None:
        table = _table().append_column("faims_cv", pa.array([-50.0, -60.0], type=pa.float32()))
        path = tmp_path / "faims.parquet"
        pq.write_table(table.replace_schema_metadata(_metadata()), path, compression="snappy")

        artifact = load_trace(path)

        assert artifact.table["faims_cv"].to_pylist() == [-50.0, -60.0]

    def test_load_rejects_non_numeric_faims_column(self, tmp_path: Path) -> None:
        table = _table().append_column("faims_cv", pa.array(["A", "B"]))
        path = tmp_path / "invalid-faims.parquet"
        pq.write_table(table.replace_schema_metadata(_metadata()), path, compression="snappy")

        with pytest.raises(ArtifactValidationError, match="faims_cv.*invalid Arrow type"):
            load_trace(path)

    def test_load_rejects_missing_required_column(self, tmp_path: Path) -> None:
        table = _table().drop(["scan_id"])
        path = tmp_path / "invalid.parquet"
        pq.write_table(table.replace_schema_metadata(_metadata()), path, compression="snappy")

        with pytest.raises(ArtifactValidationError, match="missing required columns"):
            load_trace(path)

    def test_load_rejects_null_required_value(self, tmp_path: Path) -> None:
        table = pa.table(
            {
                "scan_id": pa.array([1, None], type=pa.int32()),
                "retention_time_sec": pa.array([1.0, 2.0], type=pa.float32()),
                "ms_level": pa.array([1, 1], type=pa.int8()),
            }
        )
        path = tmp_path / "invalid.parquet"
        pq.write_table(table.replace_schema_metadata(_metadata()), path, compression="snappy")

        with pytest.raises(ArtifactValidationError, match="contains null"):
            load_trace(path)

    def test_non_strict_load_accepts_known_future_and_unknown_columns(self, tmp_path: Path) -> None:
        table = _table().append_column("injection_time_ms", pa.array([5.0, 6.0], type=pa.float32()))
        table = table.append_column("future_column", pa.array(["a", "b"], type=pa.string()))
        path = tmp_path / "future.parquet"
        pq.write_table(table.replace_schema_metadata(_metadata()), path, compression="snappy")

        with pytest.raises(ArtifactValidationError, match="not implemented"):
            load_trace(path)

        artifact = load_trace(path, strict=False)

        assert "future_column" in artifact.table.column_names
