"""Network validation for the pinned Thermo helper release asset."""

from __future__ import annotations

import hashlib

from rawtrace_qc.thermo import THERMO_HELPER_SPECIFICATION
from tests.support.network import urlopen_or_skip


class TestPinnedThermoReleaseNetwork:
    def test_published_archive_matches_pinned_sha256(self) -> None:
        digest = hashlib.sha256()
        with urlopen_or_skip(THERMO_HELPER_SPECIFICATION.download_url) as response:
            for chunk in iter(lambda: response.read(1024 * 1024), b""):
                digest.update(chunk)

        assert digest.hexdigest() == THERMO_HELPER_SPECIFICATION.sha256
