from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pytest
from rawtrace_qc.errors import ConfigurationError, ReportError
from rawtrace_qc.processing import ProcessedTable, ProcessedTableMetadata
from rawtrace_qc.report import (
    ChannelSpec,
    ReportAssetMode,
    ReportOptions,
    ReportViewMode,
    build_report,
    render_html,
    write_html,
)


def _processed_table(
    *,
    label: str = "sample.d",
    channels: tuple[str, ...] = ("total_ion_current", "base_peak_intensity"),
    faims_cv: float | str | None = None,
) -> ProcessedTable:
    values: dict[str, pa.Array] = {
        "retention_time_min": pa.array([0.5, 1.0, 1.5]),
    }
    if "total_ion_current" in channels:
        values["total_ion_current"] = pa.array([10.0, 20.0, 15.0])
    if "base_peak_intensity" in channels:
        values["base_peak_intensity"] = pa.array([2.0, 4.0, 3.0])
    return ProcessedTable(
        table=pa.table(values),
        metadata=ProcessedTableMetadata(
            rawfile_name=label,
            label=label,
            source_id=None,
            schema_version="1",
            generator="test/1.0",
            vendor="bruker",
            ms_level_file="ms1",
            extracted_at="2026-08-11T10:00:00Z",
            acquisition_start_time=None,
            acquisition_path=None,
            ms_level=1,
            faims_cv=faims_cv,
            row_granularity="spectrum",
            time_unit="min",
            precision="low",
            channels=channels,
        ),
    )


class TestReportOptions:
    def test_defaults_use_all_channels_and_embedded_assets(self) -> None:
        options = ReportOptions()

        assert options.channels is None
        assert options.asset_mode is ReportAssetMode.EMBEDDED
        assert options.initial_view is ReportViewMode.OVERLAY

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"channels": "total_ion_current"},
            {"channels": ("total_ion_current", "total_ion_current")},
            {"metadata_fields": ("unknown",)},
            {"asset_mode": "invalid"},
            {"initial_view": "invalid"},
        ],
    )
    def test_invalid_options_raise_configuration_error(
        self,
        kwargs: dict[str, object],
    ) -> None:
        with pytest.raises(ConfigurationError):
            ReportOptions(**kwargs)  # type: ignore[arg-type]


class TestBuildReport:
    def test_build_report_discovers_channels_and_metadata(self) -> None:
        report = build_report([_processed_table(faims_cv=-50.0)])

        assert [channel.key for channel in report.channels] == [
            "total_ion_current",
            "base_peak_intensity",
        ]
        assert [channel.label for channel in report.channels] == ["TIC", "BPC"]
        assert report.initial_channel == "total_ion_current"
        assert report.available_ms_levels == (1,)
        assert report.available_faims_values == (-50.0,)
        assert report.traces[0].retention_time_min == (0.5, 1.0, 1.5)
        assert report.traces[0].name == "sample.d | CV -50 V"
        assert report.traces[0].channels[0][1] == (10.0, 20.0, 15.0)
        assert report.metadata_rows[0].values[0] == ("label", "sample.d")

    def test_explicit_channels_and_metadata_fields_are_respected(self) -> None:
        report = build_report(
            [_processed_table()],
            options=ReportOptions(
                channels=("base_peak_intensity",),
                metadata_fields=("vendor", "acquisition_path"),
                initial_view=ReportViewMode.STACKED,
            ),
        )

        assert [channel.key for channel in report.channels] == ["base_peak_intensity"]
        assert report.initial_channel == "base_peak_intensity"
        assert report.initial_view is ReportViewMode.STACKED
        assert report.metadata_fields == ("vendor", "acquisition_path")
        assert report.metadata_rows[0].values == (
            ("vendor", "bruker"),
            ("acquisition_path", None),
        )

    def test_channel_spec_controls_display_label_and_axis_title(self) -> None:
        report = build_report(
            [_processed_table(channels=("total_ion_current",))],
            options=ReportOptions(
                channel_specs=(
                    ChannelSpec(
                        key="total_ion_current",
                        label="Signal",
                        y_axis_title="Counts",
                    ),
                )
            ),
        )

        assert report.channels[0].label == "Signal"
        assert report.channels[0].y_axis_title == "Counts"

    def test_missing_channel_request_raises_configuration_error(self) -> None:
        with pytest.raises(ConfigurationError, match="unavailable"):
            build_report(
                [_processed_table(channels=("total_ion_current",))],
                options=ReportOptions(channels=("base_peak_intensity",)),
            )

    def test_invalid_processed_table_is_rejected(self) -> None:
        invalid = ProcessedTable(
            table=pa.table({"total_ion_current": [1.0]}),
            metadata=_processed_table().metadata,
        )

        with pytest.raises(ReportError, match="retention_time_min"):
            build_report([invalid])


class TestHtmlReport:
    def test_render_html_contains_dynamic_tabs_metadata_and_payload(self) -> None:
        html = render_html(
            [_processed_table(faims_cv=-50.0)],
            options=ReportOptions(asset_mode=ReportAssetMode.CDN),
        )

        assert 'data-channel="total_ion_current"' in html
        assert 'data-channel="base_peak_intensity"' in html
        assert "All MS levels" not in html
        assert '"available_ms_levels":[1]' in html
        assert "dashForLevel" not in html
        assert "STACKED_TRACE_HEIGHT" in html
        assert "layout.height = stackedHeight" in html
        assert "Metadata" in html
        assert "sample.d" in html
        assert "report-faims" in html
        assert "y_axis_title" in html
        assert "https://cdn.plot.ly/plotly-" in html
        assert "retention_time_min" in html

    def test_write_html_creates_parent_and_returns_resolved_path(self, tmp_path: Path) -> None:
        output_path = write_html(
            [_processed_table(channels=("total_ion_current",))],
            tmp_path / "reports" / "qc.html",
            options=ReportOptions(asset_mode=ReportAssetMode.CDN),
        )

        assert output_path == (tmp_path / "reports" / "qc.html").resolve()
        assert output_path.is_file()
        assert output_path.read_text(encoding="utf-8").startswith("<!doctype html>")

    def test_report_without_channels_still_exposes_metadata_tab(self) -> None:
        html = render_html(
            [_processed_table(channels=())],
            options=ReportOptions(asset_mode=ReportAssetMode.CDN),
        )

        assert 'data-panel="metadata-panel"' in html
        assert 'id="report-plot"' not in html
        assert "Metadata" in html
