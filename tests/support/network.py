"""Shared helpers for network-marked tests."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from http.client import HTTPResponse
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

# A 403 can reflect facility filtering or GitHub's unauthenticated rate limit.
_SKIPPABLE_HTTP_STATUSES = {403, 407, 408, 429, 502, 503, 504}


@contextmanager
def urlopen_or_skip(url: str, *, timeout: float = 30) -> Iterator[HTTPResponse]:
    """Open a URL, skipping network or proxy failures.

    HTTP errors outside the known network/proxy cases are re-raised so a
    missing or renamed asset remains a test failure.

    Args:
        url: URL to open.
        timeout: Maximum time to wait for the response. Defaults to 30 seconds.

    Yields:
        The open HTTP response.
    """
    try:
        with urlopen(url, timeout=timeout) as response:
            yield response
    except HTTPError as error:
        if error.code in _SKIPPABLE_HTTP_STATUSES:
            pytest.skip(f"Network or proxy denied the request: {error}.")
        raise
    except OSError as error:
        pytest.skip(f"Cannot reach {url}: {error}.")
