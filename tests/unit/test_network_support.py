"""Tests for shared network-test behavior."""

from __future__ import annotations

from io import BytesIO
from urllib.error import HTTPError

import pytest
import tests.conftest as test_conftest
import tests.support.network as network_support


class _CollectedItem:
    def __init__(self, is_network: bool) -> None:
        self.keywords = {"network"} if is_network else {}
        self.markers: list[pytest.MarkDecorator] = []

    def add_marker(self, marker: pytest.MarkDecorator) -> None:
        self.markers.append(marker)


class TestUrlopenOrSkip:
    def test_yields_successful_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            network_support,
            "urlopen",
            lambda url, timeout: BytesIO(b"asset"),
        )

        with network_support.urlopen_or_skip("https://example.test/asset") as response:
            assert response.read() == b"asset"

    def test_skips_network_errors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fail_to_open(url: str, timeout: float) -> None:
            raise OSError("network unavailable")

        monkeypatch.setattr(network_support, "urlopen", fail_to_open)

        with pytest.raises(pytest.skip.Exception, match="Cannot reach"):
            with network_support.urlopen_or_skip("https://example.test/asset"):
                raise AssertionError("A failed request must not yield a response.")

    def test_skips_proxy_statuses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def proxy_denied(url: str, timeout: float) -> None:
            raise HTTPError(url, 407, "Proxy Authentication Required", None, None)

        monkeypatch.setattr(network_support, "urlopen", proxy_denied)

        with pytest.raises(pytest.skip.Exception, match="Network or proxy denied"):
            with network_support.urlopen_or_skip("https://example.test/asset"):
                raise AssertionError("A denied request must not yield a response.")

    def test_does_not_skip_missing_asset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def missing_asset(url: str, timeout: float) -> None:
            raise HTTPError(url, 404, "Not Found", None, None)

        monkeypatch.setattr(network_support, "urlopen", missing_asset)

        with pytest.raises(HTTPError) as error, network_support.urlopen_or_skip("https://example.test/missing"):
            raise AssertionError("A missing asset must not yield a response.")

        assert error.value.code == 404


class TestNetworkCollectionHook:
    def test_marks_only_network_tests_to_skip_when_offline(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(test_conftest, "_internet_reachable", lambda: False)
        network_item = _CollectedItem(is_network=True)
        unit_item = _CollectedItem(is_network=False)

        test_conftest.pytest_collection_modifyitems([network_item, unit_item])

        assert len(network_item.markers) == 1
        assert network_item.markers[0].mark.name == "skip"
        assert unit_item.markers == []
