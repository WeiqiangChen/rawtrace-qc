from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pytest


@pytest.fixture
def bruker_fixture(tmp_path: Path) -> Path:
    acquisition_path = tmp_path / "sample.d"
    acquisition_path.mkdir()
    _create_tdf(acquisition_path / "analysis.tdf")
    _create_chromatography_database(acquisition_path / "chromatography-data.sqlite")
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
        connection.execute("CREATE TABLE DiaFrameMsMsInfo (Frame INTEGER PRIMARY KEY, WindowGroup INTEGER NOT NULL)")
        connection.execute("INSERT INTO DiaFrameMsMsInfo VALUES (3, 1)")
        connection.commit()


def _create_chromatography_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE TraceSources (Id INTEGER PRIMARY KEY, Description TEXT NOT NULL)")
        connection.execute(
            "CREATE TABLE TraceChunks (Trace INTEGER NOT NULL, Times BLOB NOT NULL, Intensities BLOB NOT NULL)"
        )
        connection.execute("INSERT INTO TraceSources VALUES (?, ?)", (1, "BPC,±MS"))
        connection.execute(
            "INSERT INTO TraceChunks VALUES (?, ?, ?)",
            (
                1,
                np.asarray([1.0, 2.0, 3.0], dtype=np.float64).tobytes(),
                np.asarray([10.0, 20.0, 30.0], dtype=np.float32).tobytes(),
            ),
        )
        connection.commit()
