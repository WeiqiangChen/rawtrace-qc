"""Qt-level tests for the rawtrace-qc desktop application."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from rawtrace_qc.discovery import DiscoveryCandidate, FileFormat, Vendor
from rawtrace_qc.gui.app import _dialog_start_directory, _load_qt, create_window
from rawtrace_qc.gui.config import load_settings
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
                    widget
                    for widget in qt_application.topLevelWidgets()
                    if isinstance(widget, qt_widgets.QDialog) and widget.isVisible()
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


def test_dialog_start_directory_uses_selected_path_or_appdata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    appdata = tmp_path / "appdata"
    selected_directory = tmp_path / "selected"
    selected_directory.mkdir()
    selected_file = selected_directory / "helper.exe"
    selected_file.write_bytes(b"helper")
    monkeypatch.setattr(
        "rawtrace_qc.gui.app.default_data_directory",
        lambda: appdata,
    )

    assert _dialog_start_directory(str(selected_directory)) == str(selected_directory)
    assert _dialog_start_directory(str(selected_file)) == str(selected_directory)
    assert _dialog_start_directory(str(tmp_path / "missing")) == str(appdata)


class TestSettingsDialog:
    def test_apply_closes_without_persisting(
        self,
        tmp_path: Path,
        qt_application,
    ) -> None:
        qt_core, qt_gui, qt_widgets = _load_qt()
        settings_path = tmp_path / "settings.json"
        window = create_window(qt_core, qt_gui, qt_widgets, settings_path)
        result: dict[str, object] = {}
        dialog = None

        def inspect_dialog() -> None:
            nonlocal dialog
            try:
                dialog = next(
                    widget for widget in qt_application.topLevelWidgets() if isinstance(widget, qt_widgets.QDialog)
                )
                buttons = {button.text(): button for button in dialog.findChildren(qt_widgets.QPushButton)}
                assert {
                    "Apply",
                    "Apply and save",
                    "Cancel",
                    "Reset defaults",
                } <= buttons.keys()
                cache_edit = next(
                    edit
                    for edit in dialog.findChildren(qt_widgets.QLineEdit)
                    if edit.text() == str(window._settings.cache_directory)
                )
                cache_edit.setText(str(tmp_path / "session-cache"))
                buttons["Reset defaults"].click()
                assert cache_edit.text() == str(window._settings.cache_directory)
                assert window._settings.cache_directory != tmp_path / "session-cache"
                cache_edit.setText(str(tmp_path / "session-cache"))
                buttons["Apply"].click()
                result["applied_path"] = window._settings.cache_directory
                result["exists_after_apply"] = settings_path.exists()
                result["dialog_closed"] = not dialog.isVisible()
            except (AssertionError, AttributeError, StopIteration) as error:
                result["error"] = error
            finally:
                if dialog is not None and dialog.isVisible():
                    dialog.reject()

        QtCore.QTimer.singleShot(0, inspect_dialog)
        window._open_settings()

        assert "error" not in result
        assert result["applied_path"] == tmp_path / "session-cache"
        assert result["exists_after_apply"] is False
        assert result["dialog_closed"] is True
        window.close()

    def test_apply_and_save_closes_and_persists(
        self,
        tmp_path: Path,
        qt_application,
    ) -> None:
        qt_core, qt_gui, qt_widgets = _load_qt()
        settings_path = tmp_path / "settings.json"
        window = create_window(qt_core, qt_gui, qt_widgets, settings_path)
        result: dict[str, object] = {}
        dialog = None

        def inspect_dialog() -> None:
            nonlocal dialog
            try:
                dialog = next(
                    widget for widget in qt_application.topLevelWidgets() if isinstance(widget, qt_widgets.QDialog)
                )
                buttons = {button.text(): button for button in dialog.findChildren(qt_widgets.QPushButton)}
                cache_edit = next(
                    edit
                    for edit in dialog.findChildren(qt_widgets.QLineEdit)
                    if edit.text() == str(window._settings.cache_directory)
                )
                cache_edit.setText(str(tmp_path / "saved-cache"))
                buttons["Apply and save"].click()
                result["saved_path"] = load_settings(settings_path).cache_directory
                result["dialog_closed"] = not dialog.isVisible()
            except (AssertionError, AttributeError, StopIteration) as error:
                result["error"] = error
            finally:
                if dialog is not None and dialog.isVisible():
                    dialog.reject()

        QtCore.QTimer.singleShot(0, inspect_dialog)
        window._open_settings()

        assert "error" not in result
        assert result["saved_path"] == tmp_path / "saved-cache"
        assert result["dialog_closed"] is True
        window.close()
