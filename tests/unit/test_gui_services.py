"""Unit tests for GUI extraction, cache, helper, and report services."""

from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

import pytest
from rawtrace_qc.discovery import DiscoveryCandidate, FileFormat, Vendor
from rawtrace_qc.errors import ConfigurationError
from rawtrace_qc.extractors import BrukerExtractor
from rawtrace_qc.gui.cache import TraceCache
from rawtrace_qc.gui.config import ThermoToolSettings
from rawtrace_qc.gui.reporting import (
    ReportGenerationOptions,
    ReportStorageMode,
    generate_report,
)
from rawtrace_qc.gui.thermo import ThermoToolManager
from rawtrace_qc.report import ReportAssetMode, ReportOptions


def _bruker_candidate(path: Path) -> DiscoveryCandidate:
    return DiscoveryCandidate(path, Vendor.BRUKER, FileFormat.D)


class TestTraceCache:
    def test_extracts_once_and_loads_valid_artifacts_on_second_call(
        self,
        bruker_fixture: Path,
        tmp_path: Path,
    ) -> None:
        cache = TraceCache(tmp_path / "cache")
        candidate = _bruker_candidate(bruker_fixture)

        first = cache.extract(
            candidate,
            BrukerExtractor(),
            select_msn=False,
        )
        second = cache.extract(
            candidate,
            BrukerExtractor(),
            select_msn=False,
        )

        assert first.cache_hit is False
        assert second.cache_hit is True
        assert second.extraction == first.extraction
        assert second.extraction.ms1_path is not None
        assert second.extraction.ms1_path.is_file()

    def test_partial_cache_is_rebuilt_when_both_levels_are_requested(
        self,
        bruker_fixture: Path,
        tmp_path: Path,
    ) -> None:
        cache = TraceCache(tmp_path / "cache")
        candidate = _bruker_candidate(bruker_fixture)
        first = cache.extract(candidate, BrukerExtractor())
        assert first.extraction.msn_path is not None
        first.extraction.msn_path.unlink()

        second = cache.extract(candidate, BrukerExtractor())

        assert second.cache_hit is False
        assert second.extraction.msn_path is not None
        assert second.extraction.msn_path.is_file()


class TestThermoToolManager:
    def test_downloads_and_verifies_configured_helper(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        payload = b"thermo helper"
        monkeypatch.setattr(
            "rawtrace_qc.gui.thermo.urlopen",
            lambda url, timeout: BytesIO(payload),
        )
        settings = ThermoToolSettings(
            download_url="https://example.test/helper.exe",
            sha256=hashlib.sha256(payload).hexdigest(),
        )

        path = ThermoToolManager(settings, tmp_path / "tools").ensure_available()

        assert path.read_bytes() == payload

    def test_missing_download_configuration_is_actionable(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError, match="download_url"):
            ThermoToolManager(ThermoToolSettings(), tmp_path / "tools").ensure_available()


class TestReportGeneration:
    def test_generates_a_permanent_report_and_reuses_the_cache(
        self,
        bruker_fixture: Path,
        tmp_path: Path,
    ) -> None:
        candidate = _bruker_candidate(bruker_fixture)
        options = ReportGenerationOptions(
            storage_mode=ReportStorageMode.PERMANENT,
            output_directory=tmp_path / "reports",
            output_name="qc.html",
            report_options=ReportOptions(asset_mode=ReportAssetMode.CDN),
        )
        cache = TraceCache(tmp_path / "cache")

        first = generate_report((candidate,), cache, options=options)
        second = generate_report((candidate,), cache, options=options)

        assert first.output_path == (tmp_path / "reports" / "qc.html").resolve()
        assert first.output_path.is_file()
        assert first.processed_table_count == 2
        assert first.cache_hits == 0
        assert second.cache_hits == 1

    def test_thermo_generation_requires_helper_configuration(
        self,
        tmp_path: Path,
    ) -> None:
        candidate = DiscoveryCandidate(
            tmp_path / "sample.raw",
            Vendor.THERMO,
            FileFormat.RAW,
        )

        with pytest.raises(ConfigurationError, match="download_url"):
            generate_report((candidate,), TraceCache(tmp_path / "cache"))
