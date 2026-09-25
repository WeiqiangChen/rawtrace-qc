"""Install and locate the optional ThermScanHeaderExtractor executable."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

from rawtrace_qc.errors import ConfigurationError
from rawtrace_qc.gui.config import ThermoToolSettings
from rawtrace_qc.paths import helper_tool_directory


class ThermoToolManager:
    """Resolve or download a configured Thermo header-extractor executable."""

    def __init__(
        self,
        settings: ThermoToolSettings,
        install_directory: Path | None = None,
        release_version: str = "0.1.0",
    ) -> None:
        """Create a manager using helper settings and an optional install root.

        Args:
            settings: Thermo helper download and executable settings.
            install_directory: Explicit install directory. Defaults to None.
            release_version: Helper release version used to isolate the
                default install directory. Defaults to `"0.1.0"`.
        """
        self.settings = settings
        self.install_directory = (
            (
                Path(install_directory)
                if install_directory is not None
                else helper_tool_directory(
                    "thermoscanheaderextractor",
                    release_version,
                )
            )
            .expanduser()
            .resolve()
        )

    def ensure_available(self) -> Path:
        """Return the helper path, downloading it when configuration permits.

        Returns:
            A usable executable path.

        Raises:
            ConfigurationError: If no helper is configured, the download URL
                is invalid, downloading fails, or the checksum is wrong.
        """
        existing = self._existing_path()
        if existing is not None:
            return existing
        if self.settings.download_url is None:
            raise ConfigurationError(
                "Thermo extraction requires ThermScanHeaderExtractor. Configure "
                "thermo.download_url and optionally thermo.sha256, or set "
                "thermo.executable_path in the GUI settings."
            )
        parsed = urlparse(self.settings.download_url)
        if parsed.scheme not in {"http", "https"}:
            raise ConfigurationError(
                "Thermo helper download_url must use http or https; got "
                f"{self.settings.download_url!r}."
            )

        self.install_directory.mkdir(parents=True, exist_ok=True)
        destination = self.install_directory / self.settings.executable_name
        temporary = destination.with_suffix(destination.suffix + ".download")
        try:
            with urlopen(self.settings.download_url, timeout=60) as response:
                with temporary.open("wb") as output:
                    shutil.copyfileobj(response, output)
            self._verify_checksum(temporary)
            temporary.replace(destination)
        except (OSError, URLError) as error:
            raise ConfigurationError(
                f"Could not download ThermScanHeaderExtractor from "
                f"{self.settings.download_url!r}: {error}."
            ) from error
        finally:
            temporary.unlink(missing_ok=True)
        return destination

    def _existing_path(self) -> Path | None:
        configured = self.settings.executable_path
        if configured is not None:
            resolved = configured.expanduser().resolve()
            if resolved.is_file():
                return resolved
        installed = self.install_directory / self.settings.executable_name
        return installed if installed.is_file() else None

    def _verify_checksum(self, path: Path) -> None:
        expected = self.settings.sha256
        if expected is None:
            return
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest().casefold() != expected.casefold():
            raise ConfigurationError(
                "Downloaded ThermScanHeaderExtractor failed SHA-256 verification; "
                f"expected {expected!r}."
            )
