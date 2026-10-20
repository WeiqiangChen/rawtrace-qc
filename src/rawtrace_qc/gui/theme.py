"""Semantic colors and Qt styling for the rawtrace-qc desktop interface."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from string import Template
from typing import Any


@dataclass(frozen=True)
class Theme:
    """Store semantic colors used to style the desktop interface."""

    # Window and section surfaces
    window_background: str = "#f3f7f8"
    surface_background: str = "#ffffff"
    section_background: str = "#ffffff"

    # Input and standard button surfaces
    input_background: str = "#fbfdfd"
    button_background: str = "#e8f1f2"
    button_hover: str = "#d7ecec"

    # Text colors
    text_primary: str = "#063853"
    text_muted: str = "#78909b"
    text_disabled: str = "#9eb1bb"
    placeholder_text: str = "#78909b"

    # Header and brand colors
    header_background: str = "#063853"
    header_title: str = "#ffffff"
    header_subtitle: str = "#b7d9d9"
    accent: str = "#40B7B5"
    accent_hover: str = "#369c9a"
    accent_text: str = "#063853"

    # Primary action button colors
    primary_button: str = "#E73C40"
    primary_button_hover: str = "#c92f34"
    primary_button_text: str = "#ffffff"

    # Borders and selection colors
    border: str = "#d7e3e5"
    border_input: str = "#bfd1d5"
    border_strong: str = "#b7cdd0"
    selection_background: str = "#40B7B5"
    selection_text: str = "#063853"

    # Checkbox colors
    checkbox_border: str = "#063853"
    checkbox_background: str = "#ffffff"
    checkbox_check: str = "#40B7B5"

    # Scrollbar and splitter colors
    scrollbar_background: str = "#f3f7f8"
    scrollbar_handle: str = "#b7d9d9"
    splitter_handle: str = "#b7d9d9"

    # Section heading colors
    header_section_background: str = "#e8f1f2"
    header_section_text: str = "#063853"

    # Tooltip colors
    tooltip_background: str = "#063853"
    tooltip_text: str = "#ffffff"


LIGHT_THEME = Theme()


_STYLESHEET = Template(
    """
QWidget {
    color: $text_primary;
}
QMainWindow, QDialog, QMessageBox {
    background: $window_background;
    color: $text_primary;
}
QFrame#section, QFrame#reportBar {
    background: $section_background;
    color: $text_primary;
    border: 1px solid $border;
    border-radius: 10px;
}
QFrame#reportBar {
    background: $section_background;
    color: $text_primary;
    border-left: 5px solid $accent;
}
QFrame#header {
    background: $header_background;
    color: $header_title;
    border: 0;
    border-radius: 12px;
}
QFrame#header QLabel {
    background: transparent;
    color: $header_title;
}
QLabel#appTitle {
    color: $header_title;
    font-size: 28px;
    font-weight: 700;
}
QLabel#appSubtitle, QLabel#muted {
    color: $text_muted;
}
QFrame#header QLabel#appSubtitle {
    color: $header_subtitle;
}
QLabel#count, QLabel#subheading {
    color: $accent;
    font-weight: 700;
}
QLineEdit, QSpinBox, QDoubleSpinBox, QListWidget, QTableWidget,
QPlainTextEdit, QTextEdit, QComboBox {
    background: $input_background;
    color: $text_primary;
    border: 1px solid $border_input;
    border-radius: 6px;
    padding: 6px;
    selection-background-color: $selection_background;
    selection-color: $selection_text;
}
QLineEdit {
    placeholder-text-color: $placeholder_text;
}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
QListWidget:disabled, QTableWidget:disabled, QPlainTextEdit:disabled,
QTextEdit:disabled, QComboBox:disabled {
    background: $window_background;
    color: $text_disabled;
    border-color: $border;
}
QWidget#modeSelector {
    background: $button_background;
    color: $text_primary;
    border: 1px solid $border_strong;
    border-radius: 6px;
}
QToolButton#modeOption {
    background: transparent;
    color: $text_primary;
    border: 0;
    padding: 7px 10px;
}
QToolButton#modeOption:hover {
    background: $button_hover;
    color: $text_primary;
}
QToolButton#modeOption:checked {
    background: $accent;
    color: $accent_text;
}
QToolButton:disabled {
    background: $button_background;
    color: $text_disabled;
}
QListWidget, QTableWidget {
    padding: 2px;
}
QPushButton, QToolButton {
    background: $button_background;
    color: $text_primary;
    border: 1px solid $border_strong;
    border-radius: 6px;
    padding: 8px 13px;
    font-weight: 600;
}
QPushButton:hover, QToolButton:hover {
    background: $button_hover;
    color: $text_primary;
    border-color: $accent;
}
QPushButton:disabled, QToolButton:disabled {
    background: $button_background;
    color: $text_disabled;
    border-color: $border;
}
QPushButton#primary {
    background: $primary_button;
    color: $primary_button_text;
    border-color: $primary_button;
}
QPushButton#primary:hover {
    background: $primary_button_hover;
    color: $primary_button_text;
    border-color: $primary_button_hover;
}
QPushButton#primary:disabled {
    background: $button_background;
    color: $text_disabled;
    border-color: $border;
}
QCheckBox {
    background: transparent;
    color: $text_primary;
    spacing: 7px;
}
QCheckBox:disabled {
    background: transparent;
    color: $text_disabled;
}
QCheckBox::indicator {
    background: $checkbox_background;
    color: $checkbox_check;
    border: 1px solid $checkbox_border;
    border-radius: 3px;
    width: 15px;
    height: 15px;
}
QCheckBox::indicator:checked {
    background: $checkbox_check;
    color: $checkbox_border;
    border-color: $checkbox_border;
}
QCheckBox::indicator:disabled {
    background: $window_background;
    color: $text_disabled;
    border-color: $border;
}
QHeaderView::section {
    background: $header_section_background;
    color: $header_section_text;
    border: 0;
    font-weight: 700;
    padding: 7px;
}
QTableWidget QTableCornerButton::section {
    background: $header_section_background;
    color: $header_section_text;
    border: 0;
}
QScrollBar:vertical, QScrollBar:horizontal {
    background: $scrollbar_background;
    color: $text_primary;
    border: 0;
}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: $scrollbar_handle;
    color: $text_primary;
    border: 0;
    border-radius: 4px;
}
QScrollBar::add-line, QScrollBar::sub-line {
    background: $scrollbar_background;
    color: $text_primary;
    border: 0;
}
QSplitter::handle {
    background: $splitter_handle;
    color: $text_primary;
    height: 5px;
}
QToolTip {
    background: $tooltip_background;
    color: $tooltip_text;
    border: 1px solid $border_strong;
}
"""
)

_active_theme = LIGHT_THEME


def generate_stylesheet(theme: Theme) -> str:
    """Generate a Qt stylesheet from semantic theme colors.

    Args:
        theme: Theme whose color tokens should replace stylesheet placeholders.

    Returns:
        A complete Qt stylesheet with all theme placeholders resolved.
    """
    return _STYLESHEET.substitute(
        {field: getattr(theme, field) for field in Theme.__dataclass_fields__}
    )


def apply_theme(app_or_window: Any, theme: Theme, qt_gui: Any | None = None) -> None:
    """Apply a stylesheet and matching palette to a Qt application or widget.

    Args:
        app_or_window: Qt application or widget receiving the theme.
        theme: Semantic colors to apply.
        qt_gui: Optional loaded `PySide6.QtGui` module. If None (default), QtGui
            is imported when available.
    """
    global _active_theme
    _active_theme = theme
    app_or_window.setStyleSheet(generate_stylesheet(theme))
    if qt_gui is None:
        try:
            qt_gui = import_module("PySide6.QtGui")
        except ImportError:
            return

    palette_type = getattr(qt_gui, "QPalette", None)
    color_type = getattr(qt_gui, "QColor", None)
    if palette_type is not None and color_type is not None:
        palette = palette_type()
        roles = getattr(palette_type, "ColorRole", palette_type)
        active_role_colors = {
            "Window": theme.window_background,
            "WindowText": theme.text_primary,
            "Base": theme.input_background,
            "AlternateBase": theme.surface_background,
            "Text": theme.text_primary,
            "Button": theme.button_background,
            "ButtonText": theme.text_primary,
            "Highlight": theme.selection_background,
            "HighlightedText": theme.selection_text,
            "PlaceholderText": theme.placeholder_text,
            "ToolTipBase": theme.tooltip_background,
            "ToolTipText": theme.tooltip_text,
            "Light": theme.surface_background,
            "Mid": theme.border_strong,
            "Dark": theme.border,
        }
        disabled_role_colors = {
            **active_role_colors,
            "WindowText": theme.text_muted,
            "Base": theme.window_background,
            "Text": theme.text_disabled,
            "ButtonText": theme.text_disabled,
            "PlaceholderText": theme.text_disabled,
        }
        groups = getattr(palette_type, "ColorGroup", None)
        active = getattr(groups, "Active", None)
        inactive = getattr(groups, "Inactive", None)
        disabled = getattr(groups, "Disabled", None)
        for group in (active, inactive, disabled):
            colors = disabled_role_colors if group == disabled else active_role_colors
            for role_name, color in colors.items():
                role = getattr(roles, role_name, None)
                if role is not None:
                    if group is None:
                        palette.setColor(role, color_type(color))
                    else:
                        palette.setColor(group, role, color_type(color))
        app_or_window.setPalette(palette)

    application_type = getattr(qt_gui, "QGuiApplication", None)
    if application_type is not None:
        try:
            application = application_type.instance()
            style_hints = application.styleHints() if application is not None else None
            set_color_scheme = getattr(style_hints, "setColorScheme", None)
            if not callable(set_color_scheme):
                set_color_scheme = getattr(application_type, "setColorScheme", None)
            qt_core = import_module("PySide6.QtCore")
            scheme_type = getattr(qt_core.Qt, "ColorScheme", None)
            light_scheme = getattr(scheme_type, "Light", None)
            if callable(set_color_scheme) and light_scheme is not None:
                set_color_scheme(light_scheme)
        except (AttributeError, ImportError, RuntimeError, TypeError):
            pass


def get_active_theme() -> Theme:
    """Return the theme most recently applied to a Qt target."""
    return _active_theme
