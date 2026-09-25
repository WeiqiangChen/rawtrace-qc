"""Pinned ThermoScanHeaderExtractor release metadata."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ThermoHelperSpecification:
    """Describe one immutable ThermoScanHeaderExtractor release."""

    version: str
    asset_name: str
    download_url: str
    sha256: str
    executable_name: str


THERMO_HELPER_SPECIFICATION = ThermoHelperSpecification(
    version="0.1.0",
    asset_name="ThermoScanHeaderExtractor-v0.1.0-win-x64.zip",
    download_url=(
        "https://github.com/maxperutzlabs-ms/thermo-scan-header-extractor/"
        "releases/download/v0.1.0/ThermoScanHeaderExtractor-v0.1.0-win-x64.zip"
    ),
    sha256="d5bae1134c3d678037c68bd992fec35eef8374f996700df98294ae2cc0be939a",
    executable_name="ThermoScanHeaderExtractor.exe",
)
