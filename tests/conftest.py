from __future__ import annotations

import socket
import sqlite3
from pathlib import Path

import pytest


def _internet_reachable() -> bool:
    try:
        with socket.create_connection(("github.com", 443), timeout=2):
            return True
    except OSError:
        return False


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    network_items = [item for item in items if "network" in item.keywords]
    if not network_items or _internet_reachable():
        return
    skip_network = pytest.mark.skip(reason="no internet connection to GitHub")
    for item in network_items:
        item.add_marker(skip_network)


@pytest.fixture
def bruker_fixture(tmp_path: Path) -> Path:
    acquisition_path = tmp_path / "sample.d"
    acquisition_path.mkdir()
    _create_tdf(acquisition_path / "analysis.tdf")
    return acquisition_path


def _create_tdf(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE Frames ("
            "Id INTEGER PRIMARY KEY, Time REAL NOT NULL, Polarity TEXT NOT NULL, "
            "ScanMode INTEGER NOT NULL, MsMsType INTEGER NOT NULL, TimsId INTEGER, "
            "MaxIntensity INTEGER NOT NULL, SummedIntensities INTEGER NOT NULL, "
            "NumScans INTEGER NOT NULL, NumPeaks INTEGER NOT NULL, "
            "AccumulationTime REAL NOT NULL, RampTime REAL NOT NULL)"
        )
        connection.executemany(
            "INSERT INTO Frames VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (1, 1.0, "+", 0, 0, 1, 100, 1000, 10, 100, 5.0, 1.0),
                (2, 2.0, "+", 0, 8, 2, 200, 2000, 20, 200, 6.0, 1.0),
                (3, 3.0, "+", 0, 0, 3, 300, 3000, 30, 300, 7.0, 1.0),
            ],
        )
        connection.execute("CREATE TABLE GlobalMetadata (Key TEXT PRIMARY KEY, Value TEXT NOT NULL)")
        connection.execute(
            "INSERT INTO GlobalMetadata VALUES (?, ?)",
            ("AcquisitionDateTime", "2026-08-01T14:30:15.123+02:00"),
        )
        connection.execute(
            "INSERT INTO GlobalMetadata VALUES (?, ?)",
            ("AnalysisId", "78d629b2-0edc-4f60-b942-979a46b94ac8"),
        )
        connection.execute("CREATE TABLE DiaFrameMsMsInfo (Frame INTEGER PRIMARY KEY, WindowGroup INTEGER NOT NULL)")
        connection.execute("INSERT INTO DiaFrameMsMsInfo VALUES (3, 1)")
        connection.commit()
