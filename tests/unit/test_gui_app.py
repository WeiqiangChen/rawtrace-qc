"""Qt-level tests for the rawtrace-qc desktop application."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from rawtrace_qc.discovery import DiscoveryCandidate, FileFormat, Vendor
from rawtrace_qc.gui.app import _load_qt, create_window
from rawtrace_qc.gui.patterns import FilenamePattern, PatternMode

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtCore = pytest.importorskip("PySide6.QtCore")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture(scope="module")
def qt_application():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class TestCandidatePatterns:
    def test_editing_registered_pattern_updates_candidates_and_custom_pattern_defaults(
        self,
        tmp_path: Path,
        qt_application,
    ) -> None:
        qt_core, qt_gui, qt_widgets = _load_qt()
        window = create_window(qt_core, qt_gui, qt_widgets, tmp_path / "settings.json")
        pattern = FilenamePattern("Existing", "first", PatternMode.INCLUDE)
        window._saved_patterns = [pattern]
        window._active_pattern_keys = {(pattern.name, pattern.expression)}
        window._selection.set_candidates(
            (
                DiscoveryCandidate(tmp_path / "first.raw", Vendor.THERMO, FileFormat.RAW),
                DiscoveryCandidate(tmp_path / "second.raw", Vendor.THERMO, FileFormat.RAW),
            )
        )
        result: dict[str, object] = {}

        def inspect_dialog() -> None:
            try:
                dialog = next(
                    widget for widget in qt_application.topLevelWidgets() if isinstance(widget, qt_widgets.QDialog)
                )
                pattern_table = dialog.findChild(qt_widgets.QTableWidget)
                custom_expression = dialog.findChild(qt_widgets.QLineEdit)
                add_button = next(
                    button
                    for button in dialog.findChildren(qt_widgets.QPushButton)
                    if button.text() == "Add custom pattern"
                )
                assert pattern_table is not None
                assert custom_expression is not None
                pattern_table.item(0, 2).setText("second")
                result["after_edit"] = {
                    entry.candidate.path.name: entry.included for entry in window._selection.candidates
                }
                custom_expression.setText("first")
                add_button.click()
                mode_selector = pattern_table.cellWidget(1, 3)
                mode_group = mode_selector.findChild(qt_widgets.QButtonGroup)
                assert mode_group is not None
                result["custom"] = (
                    pattern_table.item(1, 1).text(),
                    pattern_table.item(1, 2).text(),
                    mode_group.checkedId(),
                )
                result["after_custom"] = {
                    entry.candidate.path.name: entry.included for entry in window._selection.candidates
                }
            except (AssertionError, AttributeError, StopIteration) as error:
                result["error"] = error
            finally:
                dialog.reject()

        QtCore.QTimer.singleShot(0, inspect_dialog)
        window._open_candidates()

        assert "error" not in result
        assert result["after_edit"] == {"second.raw": True, "first.raw": False}
        assert result["custom"] == ("Custom 1", "first", 0)
        assert result["after_custom"] == {"first.raw": True, "second.raw": True}
        window.close()
