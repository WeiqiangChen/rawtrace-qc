"""Tests for the Qt GUI theme foundation."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from rawtrace_qc.gui.app import _load_qt, create_window
from rawtrace_qc.gui.theme import DARK_THEME, LIGHT_THEME, Theme, apply_theme, generate_stylesheet

QtGui = pytest.importorskip("PySide6.QtGui")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture(scope="module")
def qt_application():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class TestTheme:
    def test_theme_is_frozen(self) -> None:
        assert isinstance(LIGHT_THEME, Theme)
        with pytest.raises(FrozenInstanceError):
            LIGHT_THEME.text_primary = "#000000"

    def test_dark_theme_has_dark_scheme(self) -> None:
        assert isinstance(DARK_THEME, Theme)
        assert DARK_THEME.is_dark


class TestGenerateStylesheet:
    def test_light_stylesheet_resolves_tokens_and_includes_required_widget_states(self) -> None:
        stylesheet = generate_stylesheet(LIGHT_THEME)

        assert "$" not in stylesheet
        assert "QWidget {" in stylesheet
        assert "QLineEdit:disabled" in stylesheet
        assert f"selection-background-color: {LIGHT_THEME.selection_background}" in stylesheet
        assert f"placeholder-text-color: {LIGHT_THEME.placeholder_text}" in stylesheet
        assert "QHeaderView::section" in stylesheet
        assert "QSplitter::handle" in stylesheet

    def test_dark_stylesheet_resolves_tokens(self) -> None:
        stylesheet = generate_stylesheet(DARK_THEME)

        assert "$" not in stylesheet
        assert f"background: {DARK_THEME.window_background}" in stylesheet
        assert f"color: {DARK_THEME.text_primary}" in stylesheet


class TestApplyTheme:
    def test_apply_theme_sets_stylesheet_and_palette_on_widget(self, qt_application) -> None:
        widget = QtWidgets.QWidget()

        apply_theme(widget, LIGHT_THEME, QtGui)

        assert widget.styleSheet() == generate_stylesheet(LIGHT_THEME)
        assert widget.palette().color(QtGui.QPalette.ColorRole.Window).name() == LIGHT_THEME.window_background
        assert widget.palette().color(QtGui.QPalette.ColorRole.Text).name() == LIGHT_THEME.text_primary
        widget.close()

    def test_apply_dark_theme_sets_dark_palette_values(self, qt_application) -> None:
        widget = QtWidgets.QWidget()

        apply_theme(widget, DARK_THEME, QtGui)

        assert widget.styleSheet() == generate_stylesheet(DARK_THEME)
        assert widget.palette().color(QtGui.QPalette.ColorRole.Window).name() == DARK_THEME.window_background
        assert widget.palette().color(QtGui.QPalette.ColorRole.Text).name() == DARK_THEME.text_primary
        widget.close()

    def test_create_window_applies_theme_to_uninitialized_application(self, qt_application, tmp_path) -> None:
        qt_core, qt_gui, qt_widgets = _load_qt()
        qt_application.setStyleSheet("")

        window = create_window(qt_core, qt_gui, qt_widgets, tmp_path / "settings.json")

        assert qt_application.styleSheet() == generate_stylesheet(LIGHT_THEME)
        window.close()
