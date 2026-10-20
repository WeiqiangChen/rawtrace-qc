"""PySide6 desktop interface for discovery and one-button report generation."""

from __future__ import annotations

import sys
import webbrowser
from dataclasses import replace
from importlib import import_module
from pathlib import Path
from typing import Any

from rawtrace_qc.discovery import DiscoveryScope
from rawtrace_qc.environment import default_data_directory
from rawtrace_qc.errors import ConfigurationError, DiscoveryError
from rawtrace_qc.gui.cache import TraceCache
from rawtrace_qc.gui.config import (
    GuiSettings,
    load_settings,
    save_settings,
)
from rawtrace_qc.gui.patterns import FilenamePattern, PatternMode
from rawtrace_qc.gui.reporting import (
    ReportGenerationOptions,
    ReportGenerationResult,
    ReportStorageMode,
    ReportWorkspace,
    generate_report,
)
from rawtrace_qc.gui.theme import (
    LIGHT_THEME,
    apply_theme,
    generate_stylesheet,
    get_active_theme,
)
from rawtrace_qc.gui.workflow import RawFileSelection
from rawtrace_qc.thermo import THERMO_HELPER_SPECIFICATION


def main() -> int:
    """Create the Qt application, show its main window, and run its event loop."""
    qt_core, qt_gui, qt_widgets = _load_qt()
    application = qt_widgets.QApplication.instance()
    if application is None:
        application = qt_widgets.QApplication(sys.argv)
    application.setStyle("Fusion")
    apply_theme(application, LIGHT_THEME, qt_gui)
    application.setApplicationName("rawtrace-qc")
    application.setOrganizationName("rawtrace-qc")
    window = create_window(qt_core, qt_gui, qt_widgets)
    window.show()
    return application.exec()


def create_window(
    qt_core: Any,
    qt_gui: Any,
    qt_widgets: Any,
    settings_path: Path | None = None,
) -> Any:
    """Build and return the main window using already-loaded Qt modules."""
    application = qt_widgets.QApplication.instance()
    if application is not None and application.styleSheet() != generate_stylesheet(
        LIGHT_THEME
    ):
        apply_theme(application, LIGHT_THEME, qt_gui)

    try:
        settings = load_settings(settings_path)
        configuration_message = ""
    except ConfigurationError as error:
        settings = GuiSettings()
        configuration_message = f"Configuration reset to defaults: {error}"

    class DropList(qt_widgets.QListWidget):
        """Accept local files and folders dropped from the operating system."""

        paths_dropped = qt_core.Signal(object)

        def __init__(self) -> None:
            super().__init__()
            self.setAcceptDrops(True)
            self.setDragDropMode(qt_widgets.QAbstractItemView.DragDropMode.DropOnly)

        def dragEnterEvent(self, event: Any) -> None:
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
                return
            super().dragEnterEvent(event)

        def dragMoveEvent(self, event: Any) -> None:
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
                return
            super().dragMoveEvent(event)

        def dropEvent(self, event: Any) -> None:
            paths = tuple(
                Path(url.toLocalFile())
                for url in event.mimeData().urls()
                if url.isLocalFile()
            )
            if paths:
                self.paths_dropped.emit(paths)
                event.acceptProposedAction()
                return
            super().dropEvent(event)

    class FileItemDelegate(qt_widgets.QStyledItemDelegate):
        """Paint and toggle explicit checkboxes for file list items."""

        @staticmethod
        def _checkbox_rect(option: Any) -> Any:
            """Geometry of the drawn checkbox glyph itself."""
            return qt_core.QRect(
                option.rect.left() + 4,
                option.rect.center().y() - 7,
                14,
                14,
            )

        @staticmethod
        def _checkbox_field_rect(option: Any) -> Any:
            """Clickable area: the whole reserved left column, not just the glyph."""
            return qt_core.QRect(
                option.rect.left(),
                option.rect.top(),
                24,
                option.rect.height(),
            )

        def initStyleOption(self, option: Any, index: Any) -> None:
            super().initStyleOption(option, index)
            if index.flags() & qt_core.Qt.ItemFlag.ItemIsUserCheckable:
                option.features &= (
                    ~qt_widgets.QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
                )

        def paint(
            self,
            painter: Any,
            option: Any,
            index: Any,
        ) -> None:
            if not index.flags() & qt_core.Qt.ItemFlag.ItemIsUserCheckable:
                super().paint(painter, option, index)
                return
            display_option = qt_widgets.QStyleOptionViewItem(option)
            display_option.rect.adjust(24, 0, 0, 0)
            if option.state & qt_widgets.QStyle.StateFlag.State_Selected:
                painter.fillRect(
                    self._checkbox_field_rect(option), option.palette.highlight()
                )
            super().paint(painter, display_option, index)
            rect = self._checkbox_rect(option)
            painter.save()
            painter.setRenderHint(qt_gui.QPainter.RenderHint.Antialiasing)
            theme = get_active_theme()
            painter.setPen(qt_gui.QPen(qt_gui.QColor(theme.checkbox_border), 1.2))
            painter.setBrush(qt_gui.QBrush(qt_gui.QColor(theme.checkbox_background)))
            painter.drawRoundedRect(rect, 3, 3)
            if index.data(qt_core.Qt.ItemDataRole.CheckStateRole) == (
                qt_core.Qt.CheckState.Checked.value
            ):
                painter.setPen(qt_gui.QPen(qt_gui.QColor(theme.checkbox_check), 2))
                painter.drawLine(
                    qt_core.QPoint(rect.left() + 4, rect.center().y()),
                    qt_core.QPoint(rect.center().x() - 1, rect.bottom() - 4),
                )
                painter.drawLine(
                    qt_core.QPoint(rect.center().x() - 1, rect.bottom() - 4),
                    qt_core.QPoint(rect.right() - 3, rect.top() + 4),
                )
            painter.restore()

        def editorEvent(
            self,
            event: Any,
            model: Any,
            option: Any,
            index: Any,
        ) -> bool:
            if (
                event.type() == qt_core.QEvent.Type.MouseButtonRelease
                and event.button() == qt_core.Qt.MouseButton.LeftButton
                and index.flags() & qt_core.Qt.ItemFlag.ItemIsUserCheckable
                and self._checkbox_field_rect(option).contains(
                    event.position().toPoint()
                )
            ):
                checked = index.data(qt_core.Qt.ItemDataRole.CheckStateRole) == (
                    qt_core.Qt.CheckState.Checked.value
                )
                model.setData(
                    index,
                    (
                        qt_core.Qt.CheckState.Unchecked.value
                        if checked
                        else qt_core.Qt.CheckState.Checked.value
                    ),
                    qt_core.Qt.ItemDataRole.CheckStateRole,
                )
                return True
            return super().editorEvent(event, model, option, index)

    class WorkerSignals(qt_core.QObject):
        """Carry background report results back to the GUI thread."""

        finished = qt_core.Signal(object)
        failed = qt_core.Signal(str)

    class ReportWorker(qt_core.QRunnable):
        """Run report generation without blocking the Qt event loop."""

        def __init__(self, candidates: tuple[Any, ...], options: Any) -> None:
            super().__init__()
            self.candidates = candidates
            self.options = options
            self.signals = WorkerSignals()

        def run(self) -> None:
            try:
                result = generate_report(
                    self.candidates,
                    cache,
                    options=self.options,
                    workspace=workspace,
                    thermo_settings=current_settings.thermo,
                )
            except Exception as error:
                self.signals.failed.emit(str(error))
            else:
                self.signals.finished.emit(result)

    class MainWindow(qt_widgets.QMainWindow):
        """Present discovery, selected inputs, and report controls."""

        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("rawtrace-qc | run review")
            self.resize(1180, 820)
            self.setMinimumSize(900, 620)
            self._settings = settings
            self._saved_patterns = list(settings.patterns)
            self._custom_patterns: list[FilenamePattern] = []
            self._active_pattern_keys: set[tuple[str, str]] = set()
            self._selection = RawFileSelection(settings.discovery_options())
            self._workspace = workspace
            self._cache = cache
            self._worker: Any = None
            self._rendering_candidates = False
            self._rendering_selected = False
            self._configuration_message = configuration_message
            self._build_ui()

        def _build_ui(self) -> None:
            central = qt_widgets.QWidget()
            self.setCentralWidget(central)
            root = qt_widgets.QVBoxLayout(central)
            root.setContentsMargins(28, 24, 28, 24)
            root.setSpacing(18)

            header = qt_widgets.QFrame()
            header.setObjectName("header")
            header_layout = qt_widgets.QVBoxLayout(header)
            header_layout.setContentsMargins(24, 20, 24, 20)
            title = qt_widgets.QLabel("rawtrace-qc")
            title.setObjectName("appTitle")
            subtitle = qt_widgets.QLabel("Raw-file review  /  report desk")
            subtitle.setObjectName("appSubtitle")
            header_layout.addWidget(title)
            header_layout.addWidget(subtitle)
            root.addWidget(header)

            source_frame = qt_widgets.QFrame()
            source_frame.setObjectName("section")
            source_layout = qt_widgets.QVBoxLayout(source_frame)
            source_layout.setContentsMargins(18, 16, 18, 16)
            source_heading = qt_widgets.QHBoxLayout()
            source_heading.addWidget(qt_widgets.QLabel("Discover raw files"))
            source_heading.addStretch()
            self.settings_button = qt_widgets.QPushButton("Settings")
            self.settings_button.setToolTip(
                "Configure discovery, cache, report, and Thermo helper settings"
            )
            self.settings_button.clicked.connect(self._open_settings)
            source_heading.addWidget(self.settings_button)
            source_layout.addLayout(source_heading)

            source_row = qt_widgets.QHBoxLayout()
            self.source_edit = qt_widgets.QLineEdit()
            self.source_edit.setPlaceholderText("Choose a folder to inspect")
            self.source_edit.setReadOnly(True)
            choose_source = qt_widgets.QPushButton("Choose folder")
            choose_source.clicked.connect(self._choose_source)
            self.include_subfolders = qt_widgets.QCheckBox("Include subfolders")
            self.include_subfolders.setChecked(
                self._settings.scope is DiscoveryScope.RECURSIVE
            )
            self.include_subfolders.setToolTip(
                "Search folders below the selected folder"
            )
            scan_button = qt_widgets.QPushButton("Scan folder")
            scan_button.setObjectName("primary")
            scan_button.clicked.connect(self._scan_source)
            source_row.addWidget(self.source_edit, 1)
            source_row.addWidget(choose_source)
            source_row.addWidget(self.include_subfolders)
            source_row.addWidget(scan_button)
            source_layout.addLayout(source_row)
            self.discovery_status = qt_widgets.QLabel("No folder scanned yet")
            self.discovery_status.setObjectName("muted")
            source_layout.addWidget(self.discovery_status)
            root.addWidget(source_frame)

            splitter = qt_widgets.QSplitter(qt_core.Qt.Orientation.Vertical)
            splitter.setChildrenCollapsible(False)
            root.addWidget(splitter, 1)

            selected_frame = qt_widgets.QFrame()
            selected_frame.setObjectName("section")
            selected_layout = qt_widgets.QVBoxLayout(selected_frame)
            selected_layout.setContentsMargins(18, 16, 18, 16)
            selected_heading = qt_widgets.QHBoxLayout()
            selected_heading.addWidget(qt_widgets.QLabel("Selected raw files"))
            self.selected_count = qt_widgets.QLabel("0 files")
            self.selected_count.setObjectName("count")
            selected_heading.addWidget(self.selected_count)
            selected_heading.addStretch()
            selected_layout.addLayout(selected_heading)
            self.selected_list = DropList()
            self.selected_list._file_item_delegate = FileItemDelegate(
                self.selected_list
            )
            self.selected_list.setItemDelegate(self.selected_list._file_item_delegate)
            self.selected_list.setSelectionMode(
                qt_widgets.QAbstractItemView.SelectionMode.ExtendedSelection
            )
            self.selected_list.setToolTip("Drop valid .raw files or .d folders here")
            self.selected_list.paths_dropped.connect(self._add_paths)
            self.selected_list.itemChanged.connect(self._selected_item_changed)
            selected_layout.addWidget(self.selected_list, 1)
            selected_buttons = qt_widgets.QHBoxLayout()
            remove = qt_widgets.QPushButton("Remove selected")
            remove.clicked.connect(self._remove_selected)
            select_all = qt_widgets.QPushButton("Select all")
            select_all.clicked.connect(lambda: self._set_all_selected(True))
            select_none = qt_widgets.QPushButton("Select none")
            select_none.clicked.connect(lambda: self._set_all_selected(False))
            for button in (remove, select_all, select_none):
                selected_buttons.addWidget(button)
            selected_buttons.addStretch()
            selected_layout.addLayout(selected_buttons)
            splitter.addWidget(selected_frame)

            report_frame = qt_widgets.QFrame()
            report_frame.setObjectName("reportBar")
            report_layout = qt_widgets.QHBoxLayout(report_frame)
            report_layout.setContentsMargins(18, 14, 18, 14)
            report_layout.addWidget(qt_widgets.QLabel("Report"))
            storage_selector, _, storage_buttons = _mode_selector(
                qt_core,
                qt_widgets,
                report_frame,
                ("Temporary", "Permanent"),
            )
            self.temporary_storage, self.permanent_storage = storage_buttons
            self.permanent_storage.toggled.connect(self._storage_changed)
            report_layout.addWidget(storage_selector)
            self.report_directory_edit = qt_widgets.QLineEdit(
                str(self._settings.report_directory)
            )
            self.report_directory_edit.setPlaceholderText("Permanent report directory")
            report_layout.addWidget(self.report_directory_edit, 1)
            browse_report = qt_widgets.QPushButton("Browse")
            browse_report.clicked.connect(self._choose_report_directory)
            report_layout.addWidget(browse_report)
            self.generate_button = qt_widgets.QPushButton("Generate report")
            self.generate_button.setObjectName("primary")
            self.generate_button.clicked.connect(self._generate)
            report_layout.addWidget(self.generate_button)
            root.addWidget(report_frame)
            self._storage_changed()
            if self._configuration_message:
                self.discovery_status.setText(self._configuration_message)

        def _choose_source(self) -> None:
            path = qt_widgets.QFileDialog.getExistingDirectory(
                self,
                "Choose discovery folder",
                _dialog_start_directory(self.source_edit.text()),
            )
            if path:
                self.source_edit.setText(path)
                self._clear_candidates()

        def _selected_scope(self) -> DiscoveryScope:
            """Return the discovery scope selected by the subfolder checkbox."""
            return (
                DiscoveryScope.RECURSIVE
                if self.include_subfolders.isChecked()
                else DiscoveryScope.DIRECT
            )

        def _scan_source(self) -> None:
            nonlocal current_settings
            source_text = self.source_edit.text().strip()
            if not source_text:
                self.discovery_status.setText("Choose a folder before scanning.")
                return
            try:
                scope = self._selected_scope()
                self._selection.options = replace(self._selection.options, scope=scope)
                self._settings = replace(self._settings, scope=scope)
                current_settings = self._settings
                result = self._selection.discover_folder(Path(source_text))
            except (DiscoveryError, OSError, ValueError) as error:
                self._clear_candidates()
                self.discovery_status.setText(str(error))
                return
            if not result.candidates:
                self.discovery_status.setText("No valid rawfiles were found in folder")
                return
            self.discovery_status.setText(
                f"{len(result.candidates)} valid candidate(s) found"
                + (
                    f"  /  {len(result.issues)} traversal issue(s)"
                    if result.issues
                    else ""
                )
            )
            self._open_candidates()

        def _clear_candidates(self) -> None:
            self._selection.set_candidates(())
            self.discovery_status.setText("Candidate list cleared")

        def _open_candidates(self) -> None:
            if not self._selection.candidates:
                self.discovery_status.setText("No valid rawfiles were found in folder")
                return
            dialog = qt_widgets.QDialog(self)
            dialog.setWindowTitle("Candidate raw files")
            dialog.resize(980, 700)
            layout = qt_widgets.QVBoxLayout(dialog)
            heading = qt_widgets.QHBoxLayout()
            heading.addWidget(qt_widgets.QLabel("Candidate raw files"))
            candidate_count = qt_widgets.QLabel()
            candidate_count.setObjectName("count")
            heading.addWidget(candidate_count)
            heading.addStretch()
            layout.addLayout(heading)

            pattern_title = qt_widgets.QLabel("Filename patterns")
            pattern_title.setObjectName("subheading")
            layout.addWidget(pattern_title)
            pattern_table = qt_widgets.QTableWidget(0, 4)
            pattern_table.setHorizontalHeaderLabels(("Use", "Pattern", "Regex", "Mode"))
            pattern_table.horizontalHeader().setSectionResizeMode(
                0, qt_widgets.QHeaderView.ResizeMode.ResizeToContents
            )
            pattern_table.horizontalHeader().setSectionResizeMode(
                1, qt_widgets.QHeaderView.ResizeMode.ResizeToContents
            )
            pattern_table.horizontalHeader().setSectionResizeMode(
                2, qt_widgets.QHeaderView.ResizeMode.Stretch
            )
            pattern_table.horizontalHeader().setSectionResizeMode(
                3, qt_widgets.QHeaderView.ResizeMode.ResizeToContents
            )
            layout.addWidget(pattern_table)

            custom_row = qt_widgets.QHBoxLayout()
            custom_expression = qt_widgets.QLineEdit()
            custom_expression.setPlaceholderText("Regular expression")
            add_pattern = qt_widgets.QPushButton("Add custom pattern")
            custom_row.addWidget(custom_expression, 1)
            custom_row.addWidget(add_pattern)
            layout.addLayout(custom_row)

            candidate_list = qt_widgets.QListWidget()
            candidate_list._file_item_delegate = FileItemDelegate(candidate_list)
            candidate_list.setItemDelegate(candidate_list._file_item_delegate)
            candidate_list.setSelectionMode(
                qt_widgets.QAbstractItemView.SelectionMode.ExtendedSelection
            )
            layout.addWidget(candidate_list, 1)
            candidate_buttons = qt_widgets.QHBoxLayout()
            select_all = qt_widgets.QPushButton("Select all")
            select_marked = qt_widgets.QPushButton("Select marked")
            select_none = qt_widgets.QPushButton("Select none")
            add_candidates = qt_widgets.QPushButton("Add selected to report")
            add_candidates.setObjectName("primary")
            close = qt_widgets.QPushButton("Close")
            candidate_buttons.addWidget(select_all)
            candidate_buttons.addWidget(select_marked)
            candidate_buttons.addWidget(select_none)
            candidate_buttons.addStretch()
            candidate_buttons.addWidget(add_candidates)
            candidate_buttons.addWidget(close)
            layout.addLayout(candidate_buttons)

            definitions = list(self._saved_patterns) + list(self._custom_patterns)
            saved_count = len(self._saved_patterns)

            def pattern_key(pattern: FilenamePattern) -> tuple[str, str]:
                return pattern.name, pattern.expression

            def read_rows(include_disabled: bool) -> tuple[FilenamePattern, ...] | None:
                patterns: list[FilenamePattern] = []
                try:
                    for row in range(pattern_table.rowCount()):
                        check = pattern_table.cellWidget(row, 0)
                        mode_selector = pattern_table.cellWidget(row, 3)
                        name_item = pattern_table.item(row, 1)
                        expression_item = pattern_table.item(row, 2)
                        mode_group = mode_selector.findChild(qt_widgets.QButtonGroup)
                        if (
                            name_item is None
                            or expression_item is None
                            or mode_group is None
                        ):
                            raise AttributeError("Pattern mode selector is missing.")
                        mode = (
                            PatternMode.EXCLUDE
                            if mode_group.checkedId() == 1
                            else PatternMode.INCLUDE
                        )
                        pattern = FilenamePattern(
                            name_item.text(),
                            expression_item.text(),
                            mode,
                        )
                        definitions[row] = pattern
                        if include_disabled or check.isChecked():
                            patterns.append(pattern)
                except (ConfigurationError, AttributeError) as error:
                    self.discovery_status.setText(str(error))
                    return None
                return tuple(patterns)

            def update_candidate_count() -> None:
                included = sum(entry.included for entry in self._selection.candidates)
                candidate_count.setText(
                    f"{included} active / {len(self._selection.candidates)} total"
                )

            def render_candidates() -> None:
                selected_paths = {
                    str(item.data(qt_core.Qt.ItemDataRole.UserRole))
                    for item in candidate_list.selectedItems()
                }
                self._rendering_candidates = True
                candidate_list.clear()
                for entry in self._selection.candidates:
                    item = qt_widgets.QListWidgetItem(entry.candidate.path.name)
                    path_text = str(entry.candidate.path)
                    item.setToolTip(str(entry.candidate.path))
                    item.setData(
                        qt_core.Qt.ItemDataRole.UserRole,
                        path_text,
                    )
                    if entry.included:
                        item.setFlags(
                            qt_core.Qt.ItemFlag.ItemIsEnabled
                            | qt_core.Qt.ItemFlag.ItemIsSelectable
                            | qt_core.Qt.ItemFlag.ItemIsUserCheckable
                        )
                        item.setCheckState(
                            qt_core.Qt.CheckState.Checked
                            if entry.active
                            else qt_core.Qt.CheckState.Unchecked
                        )
                    else:
                        item.setFlags(qt_core.Qt.ItemFlag.ItemIsEnabled)
                        item.setForeground(qt_gui.QBrush(qt_gui.QColor("#84909a")))
                    candidate_list.addItem(item)
                    item.setSelected(path_text in selected_paths)
                update_candidate_count()
                self._rendering_candidates = False

            def refresh_patterns() -> None:
                active = read_rows(False)
                if active is None:
                    return
                self._active_pattern_keys = {pattern_key(pattern) for pattern in active}
                self._selection.apply_patterns(active)
                render_candidates()

            def pattern_mode_selector(mode: PatternMode) -> Any:
                selector, mode_group, mode_buttons = _mode_selector(
                    qt_core,
                    qt_widgets,
                    dialog,
                    ("Include", "Exclude"),
                )
                mode_buttons[0].setChecked(mode is PatternMode.INCLUDE)
                mode_buttons[1].setChecked(mode is PatternMode.EXCLUDE)
                mode_group.buttonToggled.connect(lambda *_args: refresh_patterns())
                return selector

            def rebuild_pattern_table() -> None:
                pattern_table.blockSignals(True)
                pattern_table.setRowCount(0)
                for row, pattern in enumerate(definitions):
                    pattern_table.insertRow(row)
                    check = qt_widgets.QCheckBox()
                    check.setChecked(pattern_key(pattern) in self._active_pattern_keys)
                    check.stateChanged.connect(refresh_patterns)
                    pattern_table.setCellWidget(row, 0, check)
                    pattern_table.setItem(
                        row, 1, qt_widgets.QTableWidgetItem(pattern.name)
                    )
                    pattern_table.setItem(
                        row, 2, qt_widgets.QTableWidgetItem(pattern.expression)
                    )
                    pattern_table.setCellWidget(
                        row, 3, pattern_mode_selector(pattern.mode)
                    )
                pattern_table.blockSignals(False)

            def candidate_item_changed(item: Any) -> None:
                if self._rendering_candidates:
                    return
                path = Path(item.data(qt_core.Qt.ItemDataRole.UserRole))
                self._selection.set_candidate_active(
                    path,
                    item.checkState() == qt_core.Qt.CheckState.Checked,
                )
                update_candidate_count()

            def add_custom_pattern() -> None:
                try:
                    pattern = FilenamePattern(
                        f"Custom {len(self._custom_patterns) + 1}",
                        custom_expression.text(),
                        PatternMode.INCLUDE,
                    )
                except ConfigurationError as error:
                    qt_widgets.QMessageBox.warning(
                        dialog, "Invalid pattern", str(error)
                    )
                    return
                definitions.append(pattern)
                self._custom_patterns.append(pattern)
                self._active_pattern_keys.add(pattern_key(pattern))
                custom_expression.clear()
                rebuild_pattern_table()
                refresh_patterns()

            def promote_candidates() -> None:
                if read_rows(False) is None:
                    return
                self._selection.promote_active_candidates()
                self._refresh_selected()
                self.discovery_status.setText(
                    f"{len(self._selection.active_selected())} selected raw file(s) "
                    "active"
                )
                dialog.accept()

            def persist_pattern_definitions() -> None:
                all_patterns = read_rows(True)
                if all_patterns is None:
                    return
                self._saved_patterns = list(all_patterns[:saved_count])
                self._custom_patterns = list(all_patterns[saved_count:])
                self._settings = replace(
                    self._settings,
                    patterns=tuple(self._saved_patterns),
                )

            candidate_list.itemChanged.connect(candidate_item_changed)
            pattern_table.itemChanged.connect(lambda _item: refresh_patterns())
            select_all.clicked.connect(
                lambda: self._set_candidate_checks(True, render_candidates)
            )
            select_marked.clicked.connect(
                lambda: self._set_marked_candidate_checks(candidate_list, True)
            )
            select_none.clicked.connect(
                lambda: self._set_candidate_checks(False, render_candidates)
            )
            add_pattern.clicked.connect(add_custom_pattern)
            add_candidates.clicked.connect(promote_candidates)
            close.clicked.connect(dialog.reject)
            rebuild_pattern_table()
            refresh_patterns()
            dialog.finished.connect(lambda _: persist_pattern_definitions())
            dialog.exec()

        def _set_candidate_checks(self, active: bool, render: Any) -> None:
            for entry in self._selection.candidates:
                if entry.included:
                    self._selection.set_candidate_active(entry.candidate.path, active)
            render()

        def _set_marked_candidate_checks(
            self,
            candidate_list: Any,
            active: bool,
        ) -> None:
            """Set checked state for the currently mouse-marked candidates."""
            for item in candidate_list.selectedItems():
                if item.flags() & qt_core.Qt.ItemFlag.ItemIsUserCheckable:
                    item.setCheckState(
                        qt_core.Qt.CheckState.Checked
                        if active
                        else qt_core.Qt.CheckState.Unchecked
                    )

        def _refresh_selected(self) -> None:
            selected_paths = {
                str(item.data(qt_core.Qt.ItemDataRole.UserRole))
                for item in self.selected_list.selectedItems()
            }
            self._rendering_selected = True
            self.selected_list.clear()
            for entry in self._selection.selected:
                item = qt_widgets.QListWidgetItem(entry.candidate.path.name)
                path_text = str(entry.candidate.path)
                item.setToolTip(str(entry.candidate.path))
                item.setData(
                    qt_core.Qt.ItemDataRole.UserRole,
                    path_text,
                )
                item.setFlags(
                    qt_core.Qt.ItemFlag.ItemIsEnabled
                    | qt_core.Qt.ItemFlag.ItemIsSelectable
                    | qt_core.Qt.ItemFlag.ItemIsUserCheckable
                )
                item.setCheckState(
                    qt_core.Qt.CheckState.Checked
                    if entry.active
                    else qt_core.Qt.CheckState.Unchecked
                )
                self.selected_list.addItem(item)
                item.setSelected(path_text in selected_paths)
            self._update_selected_count()
            self._rendering_selected = False

        def _selected_item_changed(self, item: Any) -> None:
            if self._rendering_selected:
                return
            path = Path(item.data(qt_core.Qt.ItemDataRole.UserRole))
            self._selection.set_selected_active(
                path,
                item.checkState() == qt_core.Qt.CheckState.Checked,
            )
            self._update_selected_count()

        def _update_selected_count(self) -> None:
            """Refresh the active and total counts beside the selected-file list."""
            active_count = len(self._selection.active_selected())
            self.selected_count.setText(
                f"{active_count} active / {len(self._selection.selected)} files"
            )

        def _add_paths(self, paths: tuple[Path, ...]) -> None:
            result = self._selection.add_paths(paths)
            self._refresh_selected()
            messages = []
            if result.accepted:
                messages.append(f"Added {len(result.accepted)} valid path(s)")
            if result.rejected:
                messages.append(f"Rejected {len(result.rejected)} invalid path(s)")
            self.discovery_status.setText("  /  ".join(messages) or "No paths added")

        def _remove_selected(self) -> None:
            paths = tuple(
                Path(item.data(qt_core.Qt.ItemDataRole.UserRole))
                for item in self.selected_list.selectedItems()
            )
            self._selection.remove_selected(paths)
            self._refresh_selected()

        def _set_all_selected(self, active: bool) -> None:
            self._selection.set_all_selected_active(active)
            self._refresh_selected()

        def _storage_changed(self) -> None:
            permanent = self.permanent_storage.isChecked()
            self.report_directory_edit.setEnabled(permanent)

        def _choose_report_directory(self) -> None:
            path = qt_widgets.QFileDialog.getExistingDirectory(
                self,
                "Choose permanent report directory",
                _dialog_start_directory(self.report_directory_edit.text()),
            )
            if path:
                self.report_directory_edit.setText(path)

        def _generate(self) -> None:
            candidates = self._selection.active_selected()
            if not candidates:
                self.discovery_status.setText(
                    "Select at least one active raw file first."
                )
                return
            try:
                storage_mode = (
                    ReportStorageMode.PERMANENT
                    if self.permanent_storage.isChecked()
                    else ReportStorageMode.TEMPORARY
                )
                output_directory = Path(self.report_directory_edit.text())
                options = ReportGenerationOptions(
                    storage_mode=storage_mode,
                    output_directory=output_directory,
                    precision_mode="low",
                )
            except (ConfigurationError, ValueError) as error:
                self.discovery_status.setText(str(error))
                return
            self._worker = ReportWorker(candidates, options)
            self._worker.signals.finished.connect(self._report_finished)
            self._worker.signals.failed.connect(self._report_failed)
            self.generate_button.setEnabled(False)
            self.discovery_status.setText("Generating report in the background...")
            qt_core.QThreadPool.globalInstance().start(self._worker)

        def _report_finished(self, result: ReportGenerationResult) -> None:
            self._worker = None
            self.generate_button.setEnabled(True)
            self.discovery_status.setText(
                f"Report ready: {result.output_path}  /  "
                f"{result.cache_hits} cache hit(s)"
            )
            webbrowser.open(result.output_path.as_uri())

        def _report_failed(self, message: str) -> None:
            self._worker = None
            self.generate_button.setEnabled(True)
            self.discovery_status.setText(f"Report failed: {message}")

        def _open_settings(self) -> None:
            dialog = qt_widgets.QDialog(self)
            dialog.setWindowTitle("rawtrace-qc settings")
            dialog.resize(640, 430)
            layout = qt_widgets.QVBoxLayout(dialog)
            form = qt_widgets.QFormLayout()
            cache_edit = qt_widgets.QLineEdit(str(self._settings.cache_directory))
            report_edit = qt_widgets.QLineEdit(str(self._settings.report_directory))
            helper_path = qt_widgets.QLineEdit(
                str(self._settings.thermo.executable_path or "")
            )
            size_edit = qt_widgets.QLineEdit(str(int(self._settings.min_size_mb)))
            size_edit.setValidator(
                qt_gui.QRegularExpressionValidator(
                    qt_core.QRegularExpression("[0-9]*"),
                    size_edit,
                )
            )
            age_edit = qt_widgets.QLineEdit(str(self._settings.min_age_minutes))
            age_edit.setValidator(
                qt_gui.QRegularExpressionValidator(
                    qt_core.QRegularExpression("[0-9]*(\\.[0-9]*)?"),
                    age_edit,
                )
            )

            form.addRow("Minimum file size (MB)", size_edit)
            form.addRow("Minimum age (minutes)", age_edit)
            form.addRow("Trace cache", _path_editor(cache_edit, dialog, False))
            form.addRow("Permanent reports", _path_editor(report_edit, dialog, False))
            form.addRow(
                "Pinned Thermo helper",
                qt_widgets.QLabel(
                    f"v{THERMO_HELPER_SPECIFICATION.version} - "
                    f"{THERMO_HELPER_SPECIFICATION.asset_name}"
                ),
            )
            form.addRow(
                "Thermo helper executable",
                _path_editor(helper_path, dialog, True),
            )
            layout.addLayout(form)
            note = qt_widgets.QLabel(
                "When no local executable is selected, rawtrace-qc downloads the "
                "pinned archive and verifies its SHA-256 before installation."
            )
            note.setWordWrap(True)
            note.setObjectName("muted")
            layout.addWidget(note)
            button_row = qt_widgets.QHBoxLayout()
            reset_button = qt_widgets.QPushButton("Reset defaults")
            apply_button = qt_widgets.QPushButton("Apply")
            apply_save_button = qt_widgets.QPushButton("Apply and save")
            apply_save_button.setObjectName("primary")
            cancel_button = qt_widgets.QPushButton("Cancel")

            def apply_settings(persist: bool) -> None:
                self._apply_settings_dialog(
                    dialog,
                    cache_edit,
                    report_edit,
                    helper_path,
                    size_edit,
                    age_edit,
                    persist=persist,
                )

            reset_button.clicked.connect(
                lambda: self._reset_settings_dialog(
                    cache_edit,
                    report_edit,
                    helper_path,
                    size_edit,
                    age_edit,
                )
            )
            apply_button.clicked.connect(lambda: apply_settings(False))
            apply_save_button.clicked.connect(lambda: apply_settings(True))
            cancel_button.clicked.connect(dialog.reject)
            button_row.addWidget(reset_button)
            button_row.addStretch()
            button_row.addWidget(apply_save_button)
            button_row.addWidget(apply_button)
            button_row.addWidget(cancel_button)
            layout.addLayout(button_row)
            dialog.exec()

        def _apply_settings_dialog(
            self,
            dialog: Any,
            cache_edit: Any,
            report_edit: Any,
            helper_path: Any,
            size_edit: Any,
            age_edit: Any,
            persist: bool,
        ) -> None:
            nonlocal cache, current_settings
            try:
                size_text = size_edit.text().strip()
                if not size_text:
                    raise ConfigurationError(
                        "Minimum file size must be a non-negative integer."
                    )
                age_text = age_edit.text().strip()
                if not age_text:
                    raise ConfigurationError(
                        "Minimum file age must be a non-negative integer."
                    )

                updated = GuiSettings(
                    scope=self._selected_scope(),
                    min_size_mb=int(size_text),
                    min_age_minutes=float(age_text),
                    patterns=tuple(self._saved_patterns),
                    cache_directory=Path(cache_edit.text()),
                    report_directory=Path(report_edit.text()),
                    thermo=_thermo_settings(helper_path.text()),
                )
                if persist:
                    save_settings(updated, settings_path)
            except (ConfigurationError, OSError, ValueError) as error:
                qt_widgets.QMessageBox.critical(dialog, "Invalid settings", str(error))
                return
            self._settings = updated
            current_settings = updated
            self._selection.options = updated.discovery_options()
            cache = TraceCache(updated.cache_directory)
            self._cache = cache
            self.report_directory_edit.setText(str(updated.report_directory))
            dialog.accept()

        def _reset_settings_dialog(
            self,
            cache_edit: Any,
            report_edit: Any,
            helper_path: Any,
            size_edit: Any,
            age_edit: Any,
        ) -> None:
            defaults = GuiSettings()
            cache_edit.setText(str(defaults.cache_directory))
            report_edit.setText(str(defaults.report_directory))
            helper_path.clear()
            size_edit.setText(str(defaults.min_size_mb))
            age_edit.setText(str(defaults.min_age_minutes))

        def closeEvent(self, event: Any) -> None:
            if self._worker is not None:
                qt_widgets.QMessageBox.information(
                    self,
                    "Report in progress",
                    "Wait for the current report to finish before closing the "
                    "application.",
                )
                event.ignore()
                return
            self._workspace.cleanup()
            event.accept()

    workspace = ReportWorkspace()
    cache = TraceCache(settings.cache_directory)
    current_settings = settings
    window = MainWindow()
    return window


def _load_qt() -> tuple[Any, Any, Any]:
    """Load PySide6 lazily so the core package keeps Qt optional."""
    try:
        return (
            import_module("PySide6.QtCore"),
            import_module("PySide6.QtGui"),
            import_module("PySide6.QtWidgets"),
        )
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "The GUI requires PySide6. Install it with `uv sync --extra gui`."
        ) from error


def _mode_selector(
    qt_core: Any,
    qt_widgets: Any,
    parent: Any,
    labels: tuple[str, str],
) -> tuple[Any, Any, tuple[Any, Any]]:
    """Build a compact two-option selector from checkable tool buttons."""
    container = qt_widgets.QWidget(parent)
    container.setObjectName("modeSelector")
    layout = qt_widgets.QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    group = qt_widgets.QButtonGroup(container)
    group.setExclusive(True)
    first = qt_widgets.QToolButton(container)
    second = qt_widgets.QToolButton(container)
    first.setText(labels[0])
    second.setText(labels[1])
    for button in (first, second):
        button.setObjectName("modeOption")
        button.setCheckable(True)
        button.setToolButtonStyle(qt_core.Qt.ToolButtonStyle.ToolButtonTextOnly)
        layout.addWidget(button)
    group.addButton(first, 0)
    group.addButton(second, 1)
    first.setChecked(True)
    return container, group, (first, second)


def _path_editor(line_edit: Any, dialog: Any, file_mode: bool) -> Any:
    """Add a browse button beside one settings path field."""
    qt_widgets = import_module("PySide6.QtWidgets")
    container = qt_widgets.QWidget(dialog)
    layout = qt_widgets.QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    button = qt_widgets.QPushButton("Browse")

    def browse() -> None:
        start_directory = _dialog_start_directory(line_edit.text())
        if file_mode:
            path, _ = qt_widgets.QFileDialog.getOpenFileName(
                dialog, "Choose executable", start_directory
            )
        else:
            path = qt_widgets.QFileDialog.getExistingDirectory(
                dialog, "Choose directory", start_directory
            )
        if path:
            line_edit.setText(path)

    button.clicked.connect(browse)
    layout.addWidget(line_edit, 1)
    layout.addWidget(button)
    return container


def _dialog_start_directory(path_text: str) -> str:
    """Return an existing selected path or the application data directory."""
    selected_text = path_text.strip()
    if selected_text:
        selected_path = Path(selected_text).expanduser()
        if selected_path.exists():
            return str(
                selected_path if selected_path.is_dir() else selected_path.parent
            )
    return str(default_data_directory())


def _thermo_settings(executable: str) -> Any:
    """Build helper settings from the optional local executable field."""
    from rawtrace_qc.gui.config import ThermoToolSettings

    return ThermoToolSettings(
        executable_path=Path(executable.strip()) if executable.strip() else None
    )
