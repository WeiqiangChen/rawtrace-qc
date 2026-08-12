"""Prepare renderer-neutral report data from processed trace tables."""

from __future__ import annotations

import math
from collections.abc import Sequence
from numbers import Real

import pyarrow as pa

from rawtrace_qc.errors import ConfigurationError, ReportError
from rawtrace_qc.processing.models import ProcessedTable
from rawtrace_qc.report.channels import resolve_channel_spec
from rawtrace_qc.report.models import (
    ReportDocument,
    ReportMetadataRow,
    ReportOptions,
    ReportTrace,
)


def build_report(
    processed_tables: Sequence[ProcessedTable],
    *,
    options: ReportOptions | None = None,
) -> ReportDocument:
    """Build renderer-neutral report data from processed tables.

    The report layer consumes only `ProcessedTable` instances. It preserves the
    retention-time order supplied by processing and does not reopen or infer
    anything from raw files or Parquet artifacts.

    Args:
        processed_tables: Report-ready tables in the desired report order.
        options: Report configuration. If None (default), uses all available
            channels and the default metadata fields.

    Returns:
        A document that can be rendered by an HTML or future report renderer.

    Raises:
        ConfigurationError: If requested channels or the initial channel are
            unavailable, or report options are invalid.
        ReportError: If a processed table does not satisfy the report input
            contract or contains non-finite numeric values.
    """
    selected_options = options or ReportOptions()
    tables = tuple(processed_tables)
    for table_index, processed_table in enumerate(tables):
        _validate_processed_table(processed_table, table_index)

    available_channel_keys = _available_channel_keys(tables)
    selected_channel_keys = _select_channels(
        available_channel_keys,
        selected_options.channels,
    )
    initial_channel = _select_initial_channel(
        selected_channel_keys,
        selected_options.initial_channel,
    )
    channel_specs = tuple(
        resolve_channel_spec(channel, selected_options.channel_specs)
        for channel in selected_channel_keys
    )

    source_colors: dict[str, int] = {}
    traces: list[ReportTrace] = []
    metadata_rows: list[ReportMetadataRow] = []
    for table_index, processed_table in enumerate(tables):
        metadata = processed_table.metadata
        source_key = metadata.source_id or metadata.rawfile_name or metadata.label
        if source_key not in source_colors:
            source_colors[source_key] = len(source_colors)
        retention_time = tuple(
            _required_number(value, "retention_time_min", table_index)
            for value in processed_table.table["retention_time_min"].to_pylist()
        )
        table_channels = tuple(
            (
                channel,
                _channel_values(
                    processed_table,
                    channel,
                    table_index,
                ),
            )
            for channel in selected_channel_keys
            if channel in metadata.channels
        )
        name = _trace_name(processed_table, table_index)
        traces.append(
            ReportTrace(
                table_index=table_index,
                label=metadata.label,
                source_key=source_key,
                name=name,
                ms_level=metadata.ms_level,
                faims_cv=metadata.faims_cv,
                color_index=source_colors[source_key],
                retention_time_min=retention_time,
                channels=table_channels,
            )
        )
        metadata_rows.append(
            ReportMetadataRow(
                tuple(
                    (
                        field_name,
                        _metadata_value(getattr(metadata, field_name)),
                    )
                    for field_name in selected_options.metadata_fields
                )
            )
        )

    available_faims_values = _available_faims_values(tables)
    return ReportDocument(
        title=selected_options.title,
        channels=channel_specs,
        traces=tuple(traces),
        metadata_fields=selected_options.metadata_fields,
        metadata_rows=tuple(metadata_rows),
        available_ms_levels=tuple(sorted({trace.ms_level for trace in traces})),
        available_faims_values=available_faims_values,
        initial_channel=initial_channel,
        initial_view=selected_options.initial_view,
        asset_mode=selected_options.asset_mode,
    )


def _validate_processed_table(
    processed_table: ProcessedTable,
    table_index: int,
) -> None:
    if not isinstance(processed_table, ProcessedTable):
        raise ReportError(
            "Report input at index "
            f"{table_index} is {type(processed_table).__name__!r}; "
            "expected a ProcessedTable instance."
        )
    if not isinstance(processed_table.table, pa.Table):
        raise ReportError(
            f"ProcessedTable at index {table_index} does not contain an Arrow table."
        )
    if "retention_time_min" not in processed_table.table.column_names:
        raise ReportError(
            f"ProcessedTable at index {table_index} is missing the required "
            "'retention_time_min' column."
        )
    channels = processed_table.metadata.channels
    if len(set(channels)) != len(channels):
        raise ReportError(
            f"ProcessedTable at index {table_index} contains duplicate channel names."
        )
    missing_channels = set(channels) - set(processed_table.table.column_names)
    if missing_channels:
        raise ReportError(
            f"ProcessedTable at index {table_index} metadata lists channels that "
            f"are absent from the table: {', '.join(sorted(missing_channels))}."
        )


def _available_channel_keys(tables: tuple[ProcessedTable, ...]) -> tuple[str, ...]:
    available: list[str] = []
    for processed_table in tables:
        for channel in processed_table.metadata.channels:
            if channel not in available:
                available.append(channel)
    return tuple(available)


def _select_channels(
    available: tuple[str, ...],
    requested: tuple[str, ...] | None,
) -> tuple[str, ...]:
    if requested is None:
        return available
    unavailable = tuple(channel for channel in requested if channel not in available)
    if unavailable:
        raise ConfigurationError(
            "Report requested channels that are unavailable from the supplied "
            f"tables: {', '.join(unavailable)}. Available channels: "
            f"{', '.join(available) or 'none'}."
        )
    return requested


def _select_initial_channel(
    selected: tuple[str, ...],
    requested: str | None,
) -> str | None:
    if requested is None:
        return selected[0] if selected else None
    if requested not in selected:
        raise ConfigurationError(
            f"Report initial_channel {requested!r} is not among the selected "
            f"channels: {', '.join(selected) or 'none'}."
        )
    return requested


def _channel_values(
    processed_table: ProcessedTable,
    channel: str,
    table_index: int,
) -> tuple[float | None, ...]:
    return tuple(
        _optional_number(value, channel, table_index)
        for value in processed_table.table[channel].to_pylist()
    )


def _required_number(value: object, field_name: str, table_index: int) -> float:
    if not isinstance(value, Real) or isinstance(value, bool):
        raise ReportError(
            f"ProcessedTable at index {table_index} contains a non-numeric "
            f"{field_name} value {value!r}."
        )
    number = float(value)
    if not math.isfinite(number):
        raise ReportError(
            f"ProcessedTable at index {table_index} contains a non-finite "
            f"{field_name} value {value!r}."
        )
    return number


def _optional_number(
    value: object,
    channel: str,
    table_index: int,
) -> float | None:
    if value is None:
        return None
    return _required_number(value, channel, table_index)


def _metadata_value(value: object):
    if value is None or isinstance(value, (str, int, float)):
        return value
    if isinstance(value, tuple):
        return tuple(str(item) for item in value)
    return str(value)


def _available_faims_values(
    tables: tuple[ProcessedTable, ...],
) -> tuple[float | str, ...]:
    values: list[float | str] = []
    for processed_table in tables:
        value = processed_table.metadata.faims_cv
        if value is None:
            continue
        if isinstance(value, Real) and not isinstance(value, bool):
            number = float(value)
            if not math.isfinite(number):
                raise ReportError(
                    f"Report metadata contains a non-finite faims_cv {value!r}."
                )
            normalized: float | str = number
        elif isinstance(value, str):
            normalized = value
        else:
            raise ReportError(
                f"Report metadata contains an invalid faims_cv {value!r}."
            )
        if normalized not in values:
            values.append(normalized)
    numeric = sorted(value for value in values if isinstance(value, float))
    textual = sorted((value for value in values if isinstance(value, str)), key=str)
    return tuple(numeric + textual)


def _trace_name(processed_table: ProcessedTable, table_index: int) -> str:
    metadata = processed_table.metadata
    name = metadata.label
    if metadata.faims_cv is not None:
        name += f" | CV {_format_faims_value(metadata.faims_cv)}"
    if not metadata.label:
        name = f"Table {table_index + 1}"
    return name


def _format_faims_value(value: float | str) -> str:
    if isinstance(value, float):
        return f"{value:+g} V"
    return value
