"""Contract tests asserting identical behavior across all extractors."""

from __future__ import annotations

from pathlib import Path

import pytest
from rawtrace_qc.extractors import BrukerExtractor, ThermoExtractor
from rawtrace_qc.extractors.protocol import Extractor


class TestExtractorContract:
    @pytest.fixture(
        params=[
            ("bruker", "sample.d"),
            ("thermo", "sample.raw"),
        ]
    )
    def extractor_and_sample(
        self,
        request: pytest.FixtureRequest,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        bruker_fixture: Path,
    ) -> tuple[Extractor, Path]:
        vendor, filename = request.param
        if vendor == "bruker":
            return BrukerExtractor(), bruker_fixture

        input_path = tmp_path / filename
        input_path.touch()
        from rawtrace_qc.extractors import thermo as thermo_mod

        monkeypatch.setattr(
            thermo_mod,
            "locate_thermo_helper",
            lambda *args, **kwargs: tmp_path / "ThermoScanHeaderExtractor.exe",
        )
        return ThermoExtractor(), input_path

    def test_both_false_creates_no_output_and_returns_empty_result(
        self,
        extractor_and_sample: tuple[Extractor, Path],
        tmp_path: Path,
    ) -> None:
        extractor, input_path = extractor_and_sample
        output_directory = tmp_path / "no-output-dir"

        result = extractor.extract(
            input_path,
            output_directory=output_directory,
            select_ms1=False,
            select_msn=False,
        )

        assert result.ms1_path is None
        assert result.msn_path is None
        assert not output_directory.exists()

    def test_rejects_invalid_precision_mode(
        self,
        extractor_and_sample: tuple[Extractor, Path],
        tmp_path: Path,
    ) -> None:
        extractor, input_path = extractor_and_sample

        with pytest.raises(ValueError, match="precision_mode"):
            extractor.extract(
                input_path,
                output_directory=tmp_path / "out",
                precision_mode="invalid",  # type: ignore[arg-type]
            )

    def test_rejects_invalid_output_name_with_path_separators(
        self,
        extractor_and_sample: tuple[Extractor, Path],
        tmp_path: Path,
    ) -> None:
        extractor, input_path = extractor_and_sample

        with pytest.raises(ValueError, match="output_name"):
            extractor.extract(
                input_path,
                output_directory=tmp_path / "out",
                output_name="sub/name.raw",
            )

    def test_rejects_empty_output_name(
        self,
        extractor_and_sample: tuple[Extractor, Path],
        tmp_path: Path,
    ) -> None:
        extractor, input_path = extractor_and_sample

        with pytest.raises(ValueError, match="output_name"):
            extractor.extract(
                input_path,
                output_directory=tmp_path / "out",
                output_name="   ",
            )
