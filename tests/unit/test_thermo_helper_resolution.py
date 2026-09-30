from __future__ import annotations

from pathlib import Path
from urllib.error import HTTPError

import pytest
from rawtrace_qc import environment
from rawtrace_qc.errors import (
    ThermoHelperChecksumError,
    ThermoHelperDownloadError,
)
from rawtrace_qc.thermo import ThermoHelperState, ThermoHelperStatus
from tests.support import thermo_helper as resolver


def _status(
    state: ThermoHelperState,
    path: Path | None = None,
) -> ThermoHelperStatus:
    return ThermoHelperStatus(
        state=state,
        path=path,
        version=resolver.THERMO_HELPER_SPECIFICATION.version,
        license_accepted=state is ThermoHelperState.READY,
        message=f"status: {state.value}",
    )


class TestResolveIntegrationThermoHelper:
    @pytest.fixture(autouse=True)
    def force_windows_platform(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(environment, "get_platform", lambda: "win32")

    def test_uses_ready_per_user_helper_without_touching_fallback(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        executable = tmp_path / "user" / "ThermoScanHeaderExtractor.exe"
        status_calls: list[Path | None] = []

        def mock_status(*, data_directory=None, **kwargs):
            status_calls.append(data_directory)
            return _status(ThermoHelperState.READY, executable)

        monkeypatch.setattr(resolver, "get_thermo_helper_status", mock_status)
        monkeypatch.setattr(resolver, "install_thermo_helper", pytest.fail)
        monkeypatch.setattr(resolver, "accept_thermo_license", pytest.fail)
        monkeypatch.setattr(resolver, "internet_reachable", pytest.fail)

        result = resolver.resolve_integration_thermo_helper(cache_root=tmp_path / "cache")

        assert result == executable
        assert status_calls == [None]

    def test_unlicensed_user_helper_uses_warm_cache_without_actions(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        user_executable = tmp_path / "user" / "helper.exe"
        executable = tmp_path / "cache" / "helper.exe"
        status_calls = iter(
            [
                _status(ThermoHelperState.UNLICENSED, user_executable),
                _status(ThermoHelperState.READY, executable),
            ]
        )
        monkeypatch.setattr(
            resolver,
            "get_thermo_helper_status",
            lambda **kwargs: next(status_calls),
        )
        monkeypatch.setattr(resolver, "install_thermo_helper", pytest.fail)
        monkeypatch.setattr(resolver, "accept_thermo_license", pytest.fail)
        monkeypatch.setattr(resolver, "internet_reachable", pytest.fail)

        result = resolver.resolve_integration_thermo_helper(cache_root=tmp_path / "cache-root")

        assert result == executable

    def test_installs_then_accepts_only_when_each_status_requires_it(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        executable = tmp_path / "cache" / "helper.exe"
        statuses = iter(
            [
                _status(ThermoHelperState.NOT_INSTALLED),
                _status(ThermoHelperState.NOT_INSTALLED),
                _status(ThermoHelperState.UNLICENSED, executable),
                _status(ThermoHelperState.READY, executable),
            ]
        )
        install_calls: list[dict[str, object]] = []
        accept_calls: list[tuple[Path, dict[str, object]]] = []
        monkeypatch.setattr(
            resolver,
            "get_thermo_helper_status",
            lambda **kwargs: next(statuses),
        )
        monkeypatch.setattr(resolver, "internet_reachable", lambda: True)
        monkeypatch.setattr(
            resolver,
            "install_thermo_helper",
            lambda **kwargs: install_calls.append(kwargs),
        )
        monkeypatch.setattr(
            resolver,
            "accept_thermo_license",
            lambda path, **kwargs: accept_calls.append((path, kwargs)),
        )

        result = resolver.resolve_integration_thermo_helper(cache_root=tmp_path / "cache")

        assert result == executable
        assert len(install_calls) == 1
        assert install_calls[0]["data_directory"] == (tmp_path / "cache").resolve()
        assert accept_calls == [
            (
                executable,
                {
                    "data_directory": (tmp_path / "cache").resolve(),
                    "specification": resolver.THERMO_HELPER_SPECIFICATION,
                },
            )
        ]

    def test_skips_transient_http_download_failure(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        statuses = iter(
            [
                _status(ThermoHelperState.NOT_INSTALLED),
                _status(ThermoHelperState.NOT_INSTALLED),
            ]
        )
        download_error = ThermoHelperDownloadError("Temporary release outage.")
        download_error.__cause__ = HTTPError("https://example.test/helper.zip", 503, "Unavailable", None, None)
        monkeypatch.setattr(
            resolver,
            "get_thermo_helper_status",
            lambda **kwargs: next(statuses),
        )
        monkeypatch.setattr(resolver, "internet_reachable", lambda: True)
        monkeypatch.setattr(
            resolver,
            "install_thermo_helper",
            lambda **kwargs: (_ for _ in ()).throw(download_error),
        )

        with pytest.raises(pytest.skip.Exception, match="Network or proxy"):
            resolver.resolve_integration_thermo_helper(cache_root=tmp_path / "cache")

    def test_checksum_failure_is_not_skipped(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        statuses = iter(
            [
                _status(ThermoHelperState.NOT_INSTALLED),
                _status(ThermoHelperState.NOT_INSTALLED),
            ]
        )
        monkeypatch.setattr(
            resolver,
            "get_thermo_helper_status",
            lambda **kwargs: next(statuses),
        )
        monkeypatch.setattr(resolver, "internet_reachable", lambda: True)
        monkeypatch.setattr(
            resolver,
            "install_thermo_helper",
            lambda **kwargs: (_ for _ in ()).throw(ThermoHelperChecksumError("Pinned digest did not match.")),
        )

        with pytest.raises(ThermoHelperChecksumError, match="digest did not match"):
            resolver.resolve_integration_thermo_helper(cache_root=tmp_path / "cache")
