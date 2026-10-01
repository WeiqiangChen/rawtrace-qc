"""Sanity checks for the pinned Thermo helper release metadata."""

from __future__ import annotations

import hashlib

import pytest
from rawtrace_qc.thermo import THERMO_HELPER_SPECIFICATION
from tests.support.network import urlopen_or_skip


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
    def test_published_archive_matches_pinned_sha256(self) -> None:
        digest = hashlib.sha256()
        with urlopen_or_skip(THERMO_HELPER_SPECIFICATION.download_url) as response:
            for chunk in iter(lambda: response.read(1024 * 1024), b""):
                digest.update(chunk)

        assert digest.hexdigest() == THERMO_HELPER_SPECIFICATION.sha256
