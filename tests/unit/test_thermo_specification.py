"""Sanity checks for the pinned Thermo helper release metadata."""

from __future__ import annotations

from rawtrace_qc.thermo import THERMO_HELPER_SPECIFICATION


class TestThermoHelperSpecification:
    def test_pinned_release_metadata_is_internally_consistent(self) -> None:
        specification = THERMO_HELPER_SPECIFICATION

        assert len(specification.sha256) == 64
        int(specification.sha256, 16)
        assert f"v{specification.version}" in specification.asset_name
        assert f"/v{specification.version}/" in specification.download_url
        assert specification.download_url.endswith(specification.asset_name)
