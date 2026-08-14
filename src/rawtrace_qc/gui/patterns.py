"""Validate and apply filename patterns used by the desktop workflow."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from rawtrace_qc.discovery import DiscoveryCandidate
from rawtrace_qc.errors import ConfigurationError


class PatternMode(StrEnum):
    """Select whether a matching filename is included or excluded."""

    INCLUDE = "include"
    EXCLUDE = "exclude"


@dataclass(frozen=True, slots=True)
class FilenamePattern:
    """Describe one validated filename regular expression."""

    name: str
    expression: str
    mode: PatternMode = PatternMode.INCLUDE

    def __post_init__(self) -> None:
        """Validate the display name, expression, and matching mode."""
        if not isinstance(self.name, str) or not self.name.strip():
            raise ConfigurationError(
                f"Filename pattern name must be a non-empty string; got {self.name!r}."
            )
        if not isinstance(self.expression, str) or not self.expression:
            raise ConfigurationError(
                "Filename pattern expression must be a non-empty string; "
                f"got {self.expression!r}."
            )
        try:
            re.compile(self.expression)
        except re.error as error:
            raise ConfigurationError(
                f"Filename pattern {self.name!r} has invalid regular expression "
                f"{self.expression!r}: {error}."
            ) from error
        try:
            mode = PatternMode(self.mode)
        except (TypeError, ValueError) as error:
            raise ConfigurationError(
                f"Filename pattern mode {self.mode!r} is invalid; choose "
                "'include' or 'exclude'."
            ) from error
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "mode", mode)

    def matches(self, filename: str) -> bool:
        """Return whether this pattern searches successfully in `filename`."""
        return re.search(self.expression, filename) is not None


@dataclass(frozen=True, slots=True)
class FilteredCandidate:
    """Store a candidate's pattern classification and matching pattern names."""

    candidate: DiscoveryCandidate
    included: bool
    matched_pattern_names: tuple[str, ...] = ()


def filter_candidates(
    candidates: tuple[DiscoveryCandidate, ...],
    patterns: tuple[FilenamePattern, ...] = (),
) -> tuple[FilteredCandidate, ...]:
    """Classify and order candidates using active filename patterns.

    Include patterns are ORed: when at least one include pattern is active, a
    candidate must match one of them. Exclude patterns are also ORed, and any
    matching exclude pattern removes the candidate from the active group.
    Candidates are ordered with included entries first, followed by excluded
    entries, while preserving deterministic filename and path order within
    each group.

    Args:
        candidates: Valid discovery candidates to classify.
        patterns: Active filename patterns. An empty tuple leaves candidates
            included.

    Returns:
        Classified candidates in display order.
    """
    include_patterns = tuple(
        pattern for pattern in patterns if pattern.mode is PatternMode.INCLUDE
    )
    exclude_patterns = tuple(
        pattern for pattern in patterns if pattern.mode is PatternMode.EXCLUDE
    )
    classified: list[FilteredCandidate] = []
    for candidate in candidates:
        filename = candidate.path.name
        include_matches = tuple(
            pattern.name for pattern in include_patterns if pattern.matches(filename)
        )
        exclude_matches = tuple(
            pattern.name for pattern in exclude_patterns if pattern.matches(filename)
        )
        included = (not include_patterns or bool(include_matches)) and not bool(
            exclude_matches
        )
        classified.append(
            FilteredCandidate(
                candidate,
                included,
                include_matches + exclude_matches,
            )
        )
    classified.sort(
        key=lambda item: (
            not item.included,
            item.candidate.path.name.casefold(),
            str(item.candidate.path).casefold(),
        )
    )
    return tuple(classified)
