"""Channel display definitions used by report renderers."""

from __future__ import annotations

from types import MappingProxyType

from rawtrace_qc.report.models import ChannelSpec

CHANNEL_SPECS = MappingProxyType(
    {
        "total_ion_current": ChannelSpec(
            key="total_ion_current",
            label="TIC",
            y_axis_title="Intensity",
        ),
        "base_peak_intensity": ChannelSpec(
            key="base_peak_intensity",
            label="BPC",
            y_axis_title="Intensity",
        ),
    }
)


def resolve_channel_spec(
    channel: str,
    overrides: tuple[ChannelSpec, ...],
) -> ChannelSpec:
    """Resolve a display definition for a channel key.

    Args:
        channel: Processed-table column name.
        overrides: User-provided display definitions.

    Returns:
        The matching override, built-in definition, or a generated definition
        for an otherwise valid future channel.
    """
    for spec in overrides:
        if spec.key == channel:
            return spec
    if channel in CHANNEL_SPECS:
        return CHANNEL_SPECS[channel]
    return ChannelSpec(channel, _humanize_channel_name(channel))


def _humanize_channel_name(channel: str) -> str:
    return channel.replace("_", " ").title()
