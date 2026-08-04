"""Discover and validate vendor-specific raw mass-spectrometry acquisitions."""

from __future__ import annotations

from rawtrace_qc.discovery.discover import discover
from rawtrace_qc.discovery.models import (
    DiscoveryCandidate,
    DiscoveryOptions,
    DiscoveryResult,
    DiscoveryScope,
    TraversalIssue,
    TraversalTree,
)
from rawtrace_qc.discovery.policies import (
    FileFormat,
    Vendor,
    validate_bruker,
    validate_thermo,
)
from rawtrace_qc.discovery.registry import DiscoveryRegistry

__all__ = [
    "DiscoveryCandidate",
    "DiscoveryOptions",
    "DiscoveryRegistry",
    "DiscoveryResult",
    "DiscoveryScope",
    "FileFormat",
    "TraversalIssue",
    "TraversalTree",
    "Vendor",
    "discover",
    "validate_bruker",
    "validate_thermo",
]
