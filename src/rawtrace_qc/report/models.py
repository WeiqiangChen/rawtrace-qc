"""Renderer-neutral models and options for interactive reports."""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum

from rawtrace_qc.errors import ConfigurationError
from rawtrace_qc.processing.models import ProcessedTableMetadata


class ReportAssetMode(StrEnum):
    """Select how the Plotly JavaScript asset is included in the report."""

    EMBEDDED = "embedded"
    CDN = "cdn"


class ReportViewMode(StrEnum):
    """Select the initial arrangement of plot traces."""

    OVERLAY = "overlay"
    STACKED = "stacked"
    PAIRWISE = "pairwise"


@dataclass(frozen=True, slots=True)
class ChannelSpec:
    """Describe how one report channel is presented."""

    key: str
    label: str
    y_axis_title: str = "Intensity"

    def __post_init__(self) -> None:
        """Validate the channel display definition."""
        for field_name in ("key", "label", "y_axis_title"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ConfigurationError(
                    f"Report channel {field_name} must be a non-empty string; "
                    f"got {value!r}."
                )


DEFAULT_METADATA_FIELDS = (
    "label",
    "rawfile_name",
    "acquisition_start_time",
    "vendor",
    "ms_level",
    "faims_cv",
    "channels",
    "time_unit",
    "precision",
    "row_granularity",
    "source_id",
    "extracted_at",
    "generator",
    "schema_version",
)


@dataclass(frozen=True, slots=True)
class ReportOptions:
    """Configure report channels, metadata, plot behavior, and asset loading."""

    channels: tuple[str, ...] | None = None
    metadata_fields: tuple[str, ...] = DEFAULT_METADATA_FIELDS
    channel_specs: tuple[ChannelSpec, ...] = ()
    initial_channel: str | None = None
    initial_view: ReportViewMode = ReportViewMode.OVERLAY
    asset_mode: ReportAssetMode = ReportAssetMode.EMBEDDED
    title: str = "rawtrace-qc report"

    def __post_init__(self) -> None:
        """Validate report options and normalize enum and tuple values."""
        if not isinstance(self.title, str) or not self.title.strip():
            raise ConfigurationError(
                f"Report title must be a non-empty string; got {self.title!r}."
            )

        try:
            initial_view = ReportViewMode(self.initial_view)
        except (TypeError, ValueError) as error:
            raise ConfigurationError(
                f"Report initial_view {self.initial_view!r} is invalid; "
                "choose 'overlay', 'stacked', or 'pairwise'."
            ) from error
        try:
            asset_mode = ReportAssetMode(self.asset_mode)
        except (TypeError, ValueError) as error:
            raise ConfigurationError(
                f"Report asset_mode {self.asset_mode!r} is invalid; "
                "choose 'embedded' or 'cdn'."
            ) from error

        channels = _normalize_names(self.channels, "channels", allow_none=True)
        metadata_fields = (
            _normalize_names(
                self.metadata_fields,
                "metadata_fields",
                allow_none=False,
            )
            or ()
        )
        if channels is not None and len(set(channels)) != len(channels):
            raise ConfigurationError(
                f"Report channels must not contain duplicates, got {channels!r}."
            )
        if len(set(metadata_fields)) != len(metadata_fields):
            raise ConfigurationError(
                "Report metadata_fields must not contain duplicates, "
                f"got {metadata_fields!r}."
            )

        valid_metadata_fields = {field.name for field in fields(ProcessedTableMetadata)}
        invalid_metadata_fields = set(metadata_fields) - valid_metadata_fields
        if invalid_metadata_fields:
            raise ConfigurationError(
                "Report metadata_fields contain unknown fields: "
                f"{', '.join(sorted(invalid_metadata_fields))}."
            )

        channel_specs = tuple(self.channel_specs)
        if any(not isinstance(spec, ChannelSpec) for spec in channel_specs):
            raise ConfigurationError(
                "Report channel_specs must contain only ChannelSpec instances."
            )
        spec_keys = tuple(spec.key for spec in channel_specs)
        if len(set(spec_keys)) != len(spec_keys):
            raise ConfigurationError(
                "Report channel_specs must not contain duplicate keys, "
                f"got {spec_keys!r}."
            )

        if self.initial_channel is not None and (
            not isinstance(self.initial_channel, str)
            or not self.initial_channel.strip()
        ):
            raise ConfigurationError(
                "Report initial_channel must be None or a non-empty string; "
                f"got {self.initial_channel!r}."
            )

        object.__setattr__(self, "channels", channels)
        object.__setattr__(self, "metadata_fields", metadata_fields)
        object.__setattr__(self, "channel_specs", channel_specs)
        object.__setattr__(self, "initial_view", initial_view)
        object.__setattr__(self, "asset_mode", asset_mode)


@dataclass(frozen=True, slots=True)
class ReportTrace:
    """Store one processed table in renderer-neutral report form."""

    table_index: int
    label: str
    source_key: str
    name: str
    ms_level: int
    faims_cv: float | str | None
    color_index: int
    retention_time_min: tuple[float, ...]
    channels: tuple[tuple[str, tuple[float | None, ...]], ...]


ReportMetadataValue = str | int | float | None | tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReportMetadataRow:
    """Store selected metadata for one processed table."""

    values: tuple[tuple[str, ReportMetadataValue], ...]


@dataclass(frozen=True, slots=True)
class ReportDocument:
    """Hold all renderer-neutral data required for one HTML report."""

    title: str
    channels: tuple[ChannelSpec, ...]
    traces: tuple[ReportTrace, ...]
    metadata_fields: tuple[str, ...]
    metadata_rows: tuple[ReportMetadataRow, ...]
    available_ms_levels: tuple[int, ...]
    available_faims_values: tuple[float | str, ...]
    initial_channel: str | None
    initial_view: ReportViewMode
    asset_mode: ReportAssetMode


def _normalize_names(
    values: tuple[str, ...] | None,
    field_name: str,
    *,
    allow_none: bool,
) -> tuple[str, ...] | None:
    if values is None:
        if allow_none:
            return None
        raise ConfigurationError(f"Report {field_name} must be a tuple of names.")
    if isinstance(values, str):
        raise ConfigurationError(
            f"Report {field_name} must be a tuple of names, not a string."
        )
    normalized = tuple(values)
    if any(not isinstance(value, str) or not value.strip() for value in normalized):
        raise ConfigurationError(
            f"Report {field_name} must contain only non-empty strings; "
            f"got {normalized!r}."
        )
    return normalized
