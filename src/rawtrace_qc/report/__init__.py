"""Build interactive reports from processed trace tables."""

from __future__ import annotations

from rawtrace_qc.report.channels import CHANNEL_SPECS
from rawtrace_qc.report.html import render_html, write_html
from rawtrace_qc.report.models import (
    DEFAULT_METADATA_FIELDS,
    ChannelSpec,
    ReportAssetMode,
    ReportDocument,
    ReportMetadataRow,
    ReportOptions,
    ReportTrace,
    ReportViewMode,
)
from rawtrace_qc.report.prepare import build_report

__all__ = [
    "CHANNEL_SPECS",
    "DEFAULT_METADATA_FIELDS",
    "ChannelSpec",
    "ReportAssetMode",
    "ReportDocument",
    "ReportMetadataRow",
    "ReportOptions",
    "ReportTrace",
    "ReportViewMode",
    "build_report",
    "render_html",
    "write_html",
]
