"""Sanity checks for the pinned Thermo helper release metadata."""

from __future__ import annotations

import pytest
from rawtrace_qc.thermo import THERMO_HELPER_SPECIFICATION, verify_thermo_helper_archive
from tests.support.network import urlopen_or_skip
from tests.support.thermo_helper import get_or_download_thermo_helper_archive


class TestThermoHelperSpecification:
    def test_pinned_release_metadata_is_internally_consistent(self) -> None:
        specification = THERMO_HELPER_SPECIFICATION

        assert len(specification.sha256) == 64
        int(specification.sha256, 16)
        assert f"v{specification.version}" in specification.asset_name
        assert f"/v{specification.version}/" in specification.download_url
        assert specification.download_url.endswith(specification.asset_name)

    @pytest.mark.network
    def test_published_archive_is_available(self) -> None:
        with urlopen_or_skip(THERMO_HELPER_SPECIFICATION.download_url, timeout=10.0, method="HEAD") as response:
            assert response.status == 200

    @pytest.mark.network
    def test_cached_release_archive_matches_pinned_sha256(self) -> None:
        archive_path = get_or_download_thermo_helper_archive()

        assert (
            verify_thermo_helper_archive(
                archive_path,
                specification=THERMO_HELPER_SPECIFICATION
            )
            == THERMO_HELPER_SPECIFICATION.sha256
        )
