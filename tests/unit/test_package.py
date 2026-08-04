"""Unit tests for the package foundation."""

from rawtrace_qc import __version__
from rawtrace_qc.models import ExtractionResult


class TestPackage:
    def test_package_exposes_a_version(self) -> None:
        assert __version__

    def test_extraction_result_defaults_to_no_artifacts(self) -> None:
        result = ExtractionResult()

        assert result.ms1_path is None
        assert result.msn_path is None
