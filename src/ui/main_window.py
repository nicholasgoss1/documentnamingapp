"""
Main application window.
"""
import os
from typing import List

from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent, QPixmap
try:
    from PySide6.QtSvgWidgets import QSvgWidget
    _HAS_SVG = True
except ImportError:
    _HAS_SVG = False
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTableView, QLabel, QPushButton, QProgressBar, QLineEdit,
    QComboBox, QCheckBox, QMessageBox, QFileDialog, QHeaderView,
    QAbstractItemView, QInputDialog, QGroupBox, QStatusBar,
    QMenu, QMenuBar, QToolBar
)

from src.core.settings import Settings, APP_VERSION
from src.core.models import DocumentRecord, RenameStatus
from src.ui.table_model import DocumentTableModel
from src.ui.filter_proxy import DocumentFilterProxy
from src.ui.preview_widget import PdfPreviewWidget
from src.ui.worker import ProcessingWorker
from src.ui.settings_dialog import SettingsDialog
from src.ui.history_dialog import HistoryDialog
from src.ui.theme import DARK_THEME, LIGHT_THEME
from src.services.rename_service import (
    validate_batch, execute_rename_batch, undo_last_batch, export_csv
)


class MainWindow(QMainWindow):
    """Main application window with drag-and-drop, table, and preview."""

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self._worker = None
        self.setWindowTitle(f"Claim File Renamer v{APP_VERSION}")
        self.setMinimumSize(1280, 720)
        self.setAcceptDrops(True)

        self._build_menubar()
        self._build_ui()
        self._apply_theme()

        self.statusBar().showMessage("Ready. Drag and drop PDF files to begin.")

    def _build_menubar(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")
        open_act = QAction("&Open Files...", self)
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self._open_files)
        file_menu.addAction(open_act)

        export_act = QAction("&Export CSV...", self)
        export_act.setShortcut("Ctrl+E")
        export_act.triggered.connect(self._export_csv)
        file_menu.addAction(export_act)

        file_menu.addSeparator()

        quit_act = QAction("&Quit", self)
        quit_act.setShortcut("Ctrl+Q")
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        edit_menu = menubar.addMenu("&Edit")
        undo_act = QAction("&Undo Last Batch", self)
        undo_act.setShortcut("Ctrl+Z")
        undo_act.triggered.connect(self._undo_batch)
        edit_menu.addAction(undo_act)

        settings_act = QAction("&Settings...", self)
        settings_act.triggered.connect(self._open_settings)
        edit_menu.addAction(settings_act)

        view_menu = menubar.addMenu("&View")
        history_act = QAction("Rename &History", self)
        history_act.triggered.connect(self._open_history)
        view_menu.addAction(history_act)

        theme_act = QAction("Toggle &Dark Mode", self)
        theme_act.triggered.connect(self._toggle_theme)
        view_menu.addAction(theme_act)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # Top bar: search + filters
        top_bar = QHBoxLayout()

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search filenames, text, entities...")
        self._search.textChanged.connect(self._on_search)
        top_bar.addWidget(self._search, 2)

        # Filter checkboxes
        filters_group = QGroupBox("Filters")
        fl = QHBoxLayout(filters_group)
        fl.setContentsMargins(8, 4, 8, 4)

        filter_defs = [
            ("low_confidence", "Low Conf"),
            ("unsure", "UNSURE"),
            ("no_date", "NO DATE"),
            ("partial_date", "Partial Date"),
            ("missing_who", "No WHO"),
            ("missing_what", "No WHAT"),
            ("duplicates", "Duplicates"),
            ("annexure", "Annexure"),
        ]
        self._filter_checks = {}
        for name, label in filter_defs:
            cb = QCheckBox(label)
            cb.toggled.connect(lambda checked, n=name: self._on_filter(n, checked))
            fl.addWidget(cb)
            self._filter_checks[name] = cb

        top_bar.addWidget(filters_group, 3)

        # ClaimsCo logo (top right)
        logo_path = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "claimsco_logo.svg")
        logo_path = os.path.normpath(logo_path)
        if _HAS_SVG and os.path.exists(logo_path):
            self._logo = QSvgWidget(logo_path)
            self._logo.setFixedSize(200, 54)
            top_bar.addWidget(self._logo, 0, Qt.AlignRight | Qt.AlignVCenter)

        main_layout.addLayout(top_bar)

        # Main splitter: table + preview
        splitter = QSplitter(Qt.Horizontal)

        # Left: table + controls
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Table
        self._model = DocumentTableModel()
        self._proxy = DocumentFilterProxy()
        self._proxy.setSourceModel(self._model)

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.setSortingEnabled(True)
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._table_context_menu)
        self._table.selectionModel().currentRowChanged.connect(self._on_row_changed)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 5):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        for col in range(6, 10):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        # Hide Confidence Reason column — too noisy for end users
        self._table.setColumnHidden(7, True)

        left_layout.addWidget(self._table, 1)

        # Bulk actions bar
        bulk_bar = QHBoxLayout()
        bulk_bar.addWidget(QLabel("Bulk:"))

        self._bulk_who = QComboBox()
        self._bulk_who.addItems(["", "FF", "Complainant", "AFCA"])
        self._bulk_who.setPlaceholderText("Set WHO")
        self._bulk_who.currentTextChanged.connect(
            lambda v: self._bulk_set(1, v) if v else None
        )
        bulk_bar.addWidget(self._bulk_who)

        bulk_entity_btn = QPushButton("Set Entity")
        bulk_entity_btn.clicked.connect(self._bulk_set_entity)
        bulk_bar.addWidget(bulk_entity_btn)

        bulk_what_btn = QPushButton("Set WHAT")
        bulk_what_btn.clicked.connect(self._bulk_set_what)
        bulk_bar.addWidget(bulk_what_btn)

        bulk_date_btn = QPushButton("Set Date")
        bulk_date_btn.clicked.connect(self._bulk_set_date)
        bulk_bar.addWidget(bulk_date_btn)

        no_date_btn = QPushButton("NO DATE")
        no_date_btn.clicked.connect(lambda: self._bulk_set(2, "NO DATE"))
        bulk_bar.addWidget(no_date_btn)

        find_replace_btn = QPushButton("Find/Replace")
        find_replace_btn.clicked.connect(self._find_replace)
        bulk_bar.addWidget(find_replace_btn)

        lock_btn = QPushButton("Lock Selected")
        lock_btn.clicked.connect(self._lock_selected)
        bulk_bar.addWidget(lock_btn)

        remove_btn = QPushButton("Remove Selected")
        remove_btn.setObjectName("dangerButton")
        remove_btn.clicked.connect(self._remove_selected)
        bulk_bar.addWidget(remove_btn)

        bulk_bar.addStretch()
        left_layout.addLayout(bulk_bar)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        left_layout.addWidget(self._progress)

        # Bottom action bar
        action_bar = QHBoxLayout()

        self._file_count_label = QLabel("0 files loaded")
        action_bar.addWidget(self._file_count_label)
        action_bar.addStretch()

        approve_btn = QPushButton("Approve Selected")
        approve_btn.setObjectName("primaryButton")
        approve_btn.clicked.connect(self._approve_selected)
        action_bar.addWidget(approve_btn)

        approve_all_btn = QPushButton("Approve All")
        approve_all_btn.clicked.connect(self._approve_all)
        action_bar.addWidget(approve_all_btn)

        rename_btn = QPushButton("Rename Approved")
        rename_btn.setObjectName("primaryButton")
        rename_btn.clicked.connect(self._execute_rename)
        action_bar.addWidget(rename_btn)

        undo_btn = QPushButton("Undo Last Batch")
        undo_btn.setObjectName("dangerButton")
        undo_btn.clicked.connect(self._undo_batch)
        action_bar.addWidget(undo_btn)

        left_layout.addLayout(action_bar)
        splitter.addWidget(left)

        # Right: preview pane
        self._preview = PdfPreviewWidget()
        splitter.addWidget(self._preview)

        splitter.setSizes([900, 380])
        main_layout.addWidget(splitter, 1)

    def _apply_theme(self):
        dark = self.settings.get("dark_mode", True)
        self.setStyleSheet(DARK_THEME if dark else LIGHT_THEME)

    def _toggle_theme(self):
        current = self.settings.get("dark_mode", True)
        self.settings.set("dark_mode", not current)
        self._apply_theme()

    # ── Drag and Drop ──

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        files = []
        for url in urls:
            path = url.toLocalFile()
            if path.lower().endswith(".pdf"):
                files.append(path)
            elif os.path.isdir(path):
                for root, dirs, filenames in os.walk(path):
                    for fn in filenames:
                        if fn.lower().endswith(".pdf"):
                            files.append(os.path.join(root, fn))
        if files:
            self._process_files(files)
        else:
            QMessageBox.information(self, "No PDFs", "No PDF files found in the dropped items.")

    def _open_files(self):
        last_dir = self.settings.get("last_directory", "")
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select PDF Files", last_dir, "PDF Files (*.pdf)"
        )
        if files:
            self.settings.set("last_directory", os.path.dirname(files[0]))
            self._process_files(files)

    # ── Processing ──

    def _process_files(self, file_paths: List[str]):
        self._progress.setVisible(True)
        self._progress.setMaximum(len(file_paths))
        self._progress.setValue(0)
        self.statusBar().showMessage(f"Processing {len(file_paths)} files...")

        self._worker = ProcessingWorker(file_paths, self.settings)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_processing_done)
        self._worker.error.connect(self._on_processing_error)
        self._worker.start()

    def _on_progress(self, current: int, total: int):
        self._progress.setValue(current)

    def _on_processing_done(self, records: list):
        # Merge with existing records if any
        existing = self._model.get_records()
        all_records = existing + records
        self._model.set_records(all_records)
        self._progress.setVisible(False)
        count = len(all_records)
        self._file_count_label.setText(f"{count} files loaded")
        self.statusBar().showMessage(f"Done. {len(records)} new files processed. {count} total.")
        self._worker = None

    def _on_processing_error(self, msg: str):
        self._progress.setVisible(False)
        QMessageBox.critical(self, "Processing Error", msg)
        self._worker = None

    # ── Table Interactions ──

    def _on_row_changed(self, current: QModelIndex, previous: QModelIndex):
        if not current.isValid():
            self._preview.clear()
            return
        source_idx = self._proxy.mapToSource(current)
        rec = self._model.get_record(source_idx.row())
        if rec and rec.file_path:
            self._preview.load_pdf(rec.file_path)

    def _on_search(self, text: str):
        self._proxy.set_search_text(text)

    def _on_filter(self, name: str, checked: bool):
        self._proxy.set_filter(name, checked)

    def _selected_source_rows(self) -> List[int]:
        """Get selected rows mapped back to source model."""
        rows = set()
        for idx in self._table.selectionModel().selectedRows():
            source = self._proxy.mapToSource(idx)
            rows.add(source.row())
        return sorted(rows)

    def _table_context_menu(self, pos):
        menu = QMenu(self)
        rows = self._selected_source_rows()
        if not rows:
            return

        set_ff = menu.addAction("Set WHO = FF")
        set_comp = menu.addAction("Set WHO = Complainant")
        set_afca = menu.addAction("Set WHO = AFCA")
        menu.addSeparator()
        set_entity = menu.addAction("Set ENTITY...")
        set_what = menu.addAction("Set WHAT...")
        set_date = menu.addAction("Set DATE...")
        set_nodate = menu.addAction("Set NO DATE")
        menu.addSeparator()
        approve = menu.addAction("Approve")
        skip = menu.addAction("Skip")
        lock = menu.addAction("Lock / Unlock")
        menu.addSeparator()
        remove = menu.addAction("Remove")

        action = menu.exec_(self._table.viewport().mapToGlobal(pos))
        if action == set_ff:
            self._model.bulk_set_field(rows, 1, "FF")
        elif action == set_comp:
            self._model.bulk_set_field(rows, 1, "Complainant")
        elif action == set_afca:
            self._model.bulk_set_field(rows, 1, "AFCA")
        elif action == set_entity:
            self._bulk_set_entity()
        elif action == set_what:
            self._bulk_set_what()
        elif action == set_date:
            self._bulk_set_date()
        elif action == set_nodate:
            self._model.bulk_set_field(rows, 2, "NO DATE")
        elif action == approve:
            self._approve_selected()
        elif action == skip:
            for r in rows:
                rec = self._model.get_record(r)
                if rec:
                    rec.rename_status = RenameStatus.SKIPPED
                    self._model.update_record(r, rec)
        elif action == lock:
            self._lock_selected()
        elif action == remove:
            self._remove_selected()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            self._remove_selected()
        else:
            super().keyPressEvent(event)

    # ── Bulk Actions ──

    def _bulk_set(self, col: int, value: str):
        rows = self._selected_source_rows()
        if not rows:
            QMessageBox.information(self, "No Selection", "Select rows first.")
            return
        self._model.bulk_set_field(rows, col, value)

    def _bulk_set_entity(self):
        rows = self._selected_source_rows()
        if not rows:
            return
        entities = self.settings.get("preferred_entities", [])
        entity, ok = QInputDialog.getItem(
            self, "Set Entity", "Select entity:", [""] + entities, 0, True
        )
        if ok:
            self._model.bulk_set_field(rows, 3, entity)

    def _bulk_set_what(self):
        rows = self._selected_source_rows()
        if not rows:
            return
        labels = self.settings.get("preferred_doc_labels", [])
        what, ok = QInputDialog.getItem(
            self, "Set WHAT", "Select document type:", [""] + labels, 0, True
        )
        if ok:
            self._model.bulk_set_field(rows, 4, what)

    def _bulk_set_date(self):
        rows = self._selected_source_rows()
        if not rows:
            return
        date, ok = QInputDialog.getText(
            self, "Set Date", "Enter date (dd.mm.yyyy or NO DATE):"
        )
        if ok:
            self._model.bulk_set_field(rows, 2, date)

    def _find_replace(self):
        rows = self._selected_source_rows()
        if not rows:
            QMessageBox.information(self, "No Selection", "Select rows first.")
            return
        find, ok = QInputDialog.getText(self, "Find", "Find text:")
        if not ok or not find:
            return
        replace, ok = QInputDialog.getText(self, "Replace", "Replace with:")
        if not ok:
            return
        self._model.find_replace(rows, find, replace)

    def _remove_selected(self):
        rows = self._selected_source_rows()
        if not rows:
            QMessageBox.information(self, "No Selection", "Select rows to remove.")
            return
        reply = QMessageBox.question(
            self, "Remove Documents",
            f"Remove {len(rows)} document(s) from the list?\n\n"
            "This only removes them from the table, not from disk.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        self._model.remove_records(rows)
        count = len(self._model.get_records())
        self._file_count_label.setText(f"{count} files loaded")
        self.statusBar().showMessage(f"{len(rows)} documents removed. {count} remaining.")

    def _lock_selected(self):
        rows = self._selected_source_rows()
        for r in rows:
            rec = self._model.get_record(r)
            if rec:
                rec.locked = not rec.locked
                self._model.update_record(r, rec)

    # ── Approve / Rename ──

    def _approve_selected(self):
        rows = self._selected_source_rows()
        for r in rows:
            rec = self._model.get_record(r)
            if rec and rec.rename_status == RenameStatus.PENDING:
                rec.rename_status = RenameStatus.APPROVED
                self._model.update_record(r, rec)
        self.statusBar().showMessage(f"{len(rows)} files approved.")

    def _approve_all(self):
        records = self._model.get_records()
        count = 0
        for i, rec in enumerate(records):
            if rec.rename_status == RenameStatus.PENDING:
                rec.rename_status = RenameStatus.APPROVED
                count += 1
        self._model.set_records(records)
        self.statusBar().showMessage(f"{count} files approved.")

    def _execute_rename(self):
        records = self._model.get_records()
        approved = [r for r in records if r.rename_status == RenameStatus.APPROVED]
        if not approved:
            QMessageBox.information(self, "Nothing to Rename", "No approved files to rename.")
            return

        # Validate
        errors = validate_batch(records)
        if errors:
            msg = "Validation errors:\n"
            for idx, err in errors[:10]:
                msg += f"  Row {idx}: {err}\n"
            if len(errors) > 10:
                msg += f"  ... and {len(errors) - 10} more\n"
            QMessageBox.warning(self, "Validation Errors", msg)
            return

        # Confirm
        reply = QMessageBox.question(
            self, "Confirm Rename",
            f"Rename {len(approved)} files?\n\nThis will rename files on disk. "
            "A rollback manifest will be saved for undo.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        success, err_count, manifest = execute_rename_batch(records)
        self._model.set_records(records)
        self.statusBar().showMessage(
            f"Renamed {success} files. {err_count} errors. Manifest: {manifest}"
        )
        if err_count > 0:
            QMessageBox.warning(
                self, "Rename Errors",
                f"{err_count} files had errors. Check the status column for details."
            )

    def _undo_batch(self):
        reply = QMessageBox.question(
            self, "Undo Last Batch",
            "This will undo the most recent rename batch. Continue?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        success, errors, msg = undo_last_batch()
        QMessageBox.information(self, "Undo Result", msg)
        self.statusBar().showMessage(msg)

    def _export_csv(self):
        records = self._model.get_records()
        if not records:
            QMessageBox.information(self, "No Data", "No records to export.")
            return
        path = export_csv(records)
        QMessageBox.information(self, "Export Complete", f"CSV exported to:\n{path}")
        self.statusBar().showMessage(f"Exported to {path}")

    def _open_settings(self):
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec_():
            self._apply_theme()

    def _open_history(self):
        dlg = HistoryDialog(self)
        dlg.exec_()
