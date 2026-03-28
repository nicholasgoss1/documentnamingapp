"""
Claude Extraction Pack tab — Groq-assisted verbatim extraction for AFCA drafting.
Accepts drag-and-drop PDFs, generates structured VP1-VP6 Verbatim Pack.
"""
import os
import datetime
from collections import defaultdict
from typing import Dict, List, Optional

import fitz  # PyMuPDF

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QProgressBar, QTextEdit, QFileDialog, QGroupBox,
    QMessageBox, QApplication, QFrame, QSplitter,
    QListWidget, QListWidgetItem,
)

from src.services.smart_extractor import smart_extractor, VP_SECTIONS


class DropZone(QFrame):
    """Dashed-border drop zone for PDFs."""
    files_dropped = Signal(list)
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(100)
        self.setStyleSheet(
            "QFrame { border: 2px dashed #45475a; border-radius: 12px; }"
        )
        self.setCursor(Qt.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        self._label = QLabel("Drop PDFs here\nor click to browse")
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setObjectName("subtitleLabel")
        layout.addWidget(self._label)
        self._count = QLabel("")
        self._count.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._count)

    def set_count(self, n: int):
        self._count.setText(f"{n} files loaded" if n else "")

    def mousePressEvent(self, event):
        self.clicked.emit()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        files = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".pdf"):
                files.append(path)
            elif os.path.isdir(path):
                for root, _, fns in os.walk(path):
                    for fn in fns:
                        if fn.lower().endswith(".pdf"):
                            files.append(os.path.join(root, fn))
        if files:
            self.files_dropped.emit(files)


class ExtractionWorker(QThread):
    """Background worker that processes PDFs through SmartExtractor."""
    progress = Signal(int, int)
    status_msg = Signal(str)
    finished = Signal(str, dict)
    error = Signal(str)

    def __init__(self, files: list, matter_ref: str, date_of_loss: str, parent=None):
        super().__init__(parent)
        self._files = files
        self._matter_ref = matter_ref
        self._date_of_loss = date_of_loss

    def run(self):
        try:
            total = len(self._files)
            if not total:
                self.error.emit("No PDF files to process.")
                return

            vp_results: Dict[str, list] = defaultdict(list)
            ai_count = 0
            fallback_files: list = []

            for idx, filepath in enumerate(self._files):
                filename = os.path.basename(filepath)
                self.progress.emit(idx + 1, total)
                self.status_msg.emit(f"Processing {filename} \u2014 extracting text...")

                try:
                    doc = fitz.open(filepath)
                    text_parts = []
                    for page in doc:
                        text_parts.append(page.get_text("text"))
                    full_text = "\n".join(text_parts)
                    doc.close()
                except Exception as e:
                    vp_results["VP_OTHER"].append({
                        "filename": filename, "doc_type": "Unknown", "who": "Unknown",
                        "passages": [{"section": f"[ERROR: {e}]", "page": "UNKNOWN", "text": ""}],
                        "fallback": True, "used_groq": False,
                    })
                    fallback_files.append(filename)
                    continue

                self.status_msg.emit(f"Processing {filename} \u2014 classifying...")
                result = smart_extractor.process_document(full_text, filename)
                vp = result.get("vp_section", "VP_OTHER")
                vp_results[vp].append(result)
                if result.get("used_groq"):
                    ai_count += 1
                if result.get("fallback"):
                    fallback_files.append(filename)

            pack_text = self._build_pack(vp_results, ai_count, total, fallback_files)
            summary = {
                "total": total, "ai_count": ai_count,
                "fallback_count": len(fallback_files),
                "fallback_files": fallback_files,
                "vp_populated": {
                    vp: bool(vp_results.get(vp))
                    for vp in ["VP1", "VP2", "VP3", "VP4", "VP5", "VP6"]
                },
            }
            self.finished.emit(pack_text, summary)
        except Exception as e:
            self.error.emit(str(e))

    def _build_pack(self, vp_results, ai_count, total, fallback_files) -> str:
        now = datetime.datetime.now()
        lines = []
        lines.append("=" * 64)
        lines.append("CLAIMSCO PTY LTD \u2014 VERBATIM PACK")
        lines.append(f"Matter: {self._matter_ref or '(not specified)'}")
        lines.append(f"Date of loss: {self._date_of_loss or '(not specified)'}")
        lines.append(f"Generated: {now.strftime('%d %B %Y %H:%M')}")
        lines.append(f"Documents: {total} | AI-assisted: {ai_count}")
        lines.append("=" * 64)
        lines.append("")

        vp_order = ["VP1", "VP2", "VP3", "VP4", "VP5", "VP6", "VP_OTHER"]
        vp_labels = {
            "VP1": ("VP1 \u2014 PDS QUOTABLE SECTIONS", "PDS"),
            "VP2": ("VP2 \u2014 COMPLAINANT EXPERT REPORTS", "COMPLAINANT EXPERT"),
            "VP3": ("VP3 \u2014 FF EXPERT REPORTS AND DECISIONS", "FF DECISION"),
            "VP4": ("VP4 \u2014 SCOPES AND QUOTES", "SCOPE"),
            "VP5": ("VP5 \u2014 WEATHER EVIDENCE", "WEATHER"),
            "VP6": ("VP6 \u2014 SOLAR AND SPECIALIST REPORTS", "SPECIALIST"),
            "VP_OTHER": ("OTHER DOCUMENTS", "OTHER"),
        }

        for vp in vp_order:
            results = vp_results.get(vp, [])
            if not results:
                continue
            title, default_label = vp_labels.get(vp, (vp, vp))
            lines.append("")
            lines.append(f"## {title}")
            lines.append("")
            for result in results:
                fn = result.get("filename", "")
                who = result.get("who", "")
                label = f"{who} {default_label}" if who and who != "Unknown" else default_label
                for passage in result.get("passages", []):
                    page = passage.get("page", "UNKNOWN")
                    section = passage.get("section", "")
                    text = passage.get("text", "")
                    lines.append(f"--- {label} | {fn} | Page {page} ---")
                    if section:
                        lines.append(f"SECTION: {section}")
                    lines.append(f"TEXT:")
                    if text:
                        lines.append(text)
                    lines.append("---")
                    lines.append("")

        if fallback_files:
            lines.append("")
            lines.append("## GAPS \u2014 MANUAL REVIEW REQUIRED")
            lines.append("")
            lines.append("The following documents used raw text (Groq unavailable or failed).")
            lines.append("Verify these manually before uploading to Claude:")
            for fn in fallback_files:
                lines.append(f"  - {fn}")
            lines.append("")
            lines.append("=" * 64)

        return "\n".join(lines)


class ExtractionTab(QWidget):
    """Tab 3 — Claude Extraction Pack with Groq-assisted smart extraction."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._files: List[str] = []
        self._worker: Optional[ExtractionWorker] = None
        self._pack_text = ""
        self._build_ui()

    def load_files(self, paths: list):
        """Public method to load files from another tab."""
        self._add_files(paths)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # Top: drop zone + file list + matter details
        top = QSplitter(Qt.Horizontal)
        self._drop_zone = DropZone()
        self._drop_zone.files_dropped.connect(self._add_files)
        self._drop_zone.clicked.connect(self._browse_files)
        top.addWidget(self._drop_zone)

        # File list panel (middle)
        file_panel = QWidget()
        fp_layout = QVBoxLayout(file_panel)
        fp_layout.setContentsMargins(0, 0, 0, 0)
        fp_header = QHBoxLayout()
        fp_header.addWidget(QLabel("Files"))
        self._files_select_btn = QPushButton("\u2611 All")
        self._files_select_btn.setFixedHeight(24)
        self._files_select_btn.setFixedWidth(50)
        self._files_select_btn.clicked.connect(self._toggle_files_select)
        fp_header.addWidget(self._files_select_btn)
        remove_btn = QPushButton("Remove Sel.")
        remove_btn.setFixedHeight(24)
        remove_btn.clicked.connect(self._remove_selected_files)
        fp_header.addWidget(remove_btn)
        fp_layout.addLayout(fp_header)
        self._file_list = QListWidget()
        self._file_list.setStyleSheet("""
            QListWidget::indicator {
                width: 14px; height: 14px;
                border: 2px solid #89b4fa; border-radius: 2px;
                background: #313244;
            }
            QListWidget::indicator:checked {
                background: #89b4fa; border-color: #89b4fa;
            }
        """)
        fp_layout.addWidget(self._file_list)
        top.addWidget(file_panel)

        # Matter details (right)
        details = QGroupBox("Matter Details")
        dl = QVBoxLayout(details)
        mr = QHBoxLayout()
        mr.addWidget(QLabel("Matter Ref:"))
        self._matter_edit = QLineEdit()
        self._matter_edit.setPlaceholderText("MAT-2026-0042")
        mr.addWidget(self._matter_edit, 1)
        dl.addLayout(mr)
        dol = QHBoxLayout()
        dol.addWidget(QLabel("Date of Loss:"))
        self._dol_edit = QLineEdit()
        self._dol_edit.setPlaceholderText("31 October 2024")
        dol.addWidget(self._dol_edit, 1)
        dl.addLayout(dol)
        dl.addStretch()
        top.addWidget(details)
        top.setSizes([250, 200, 200])
        root.addWidget(top)

        # Generate button + progress
        gen_row = QHBoxLayout()
        self._gen_btn = QPushButton("Generate Verbatim Pack \u25B6")
        self._gen_btn.setObjectName("primaryButton")
        self._gen_btn.setEnabled(False)
        self._gen_btn.clicked.connect(self._generate)
        gen_row.addWidget(self._gen_btn)
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setTextVisible(True)
        gen_row.addWidget(self._progress, 1)
        root.addLayout(gen_row)

        # VP status row
        self._vp_row = QWidget()
        self._vp_layout = QHBoxLayout(self._vp_row)
        self._vp_layout.setContentsMargins(0, 0, 0, 0)
        self._vp_labels: Dict[str, QLabel] = {}
        for vp in ["VP1", "VP2", "VP3", "VP4", "VP5", "VP6"]:
            short = {"VP1": "PDS", "VP2": "Expert", "VP3": "FF",
                     "VP4": "Scope", "VP5": "Weather", "VP6": "Specialist"}[vp]
            lbl = QLabel(f"{vp} {short}")
            lbl.setStyleSheet("padding: 4px 8px; border-radius: 8px; background: #313244;")
            self._vp_labels[vp] = lbl
            self._vp_layout.addWidget(lbl)
        self._vp_layout.addStretch()
        self._vp_row.setVisible(False)
        root.addWidget(self._vp_row)

        # Warning banner
        self._warn = QLabel("")
        self._warn.setWordWrap(True)
        self._warn.setStyleSheet("padding: 6px; border: 1px solid #f38ba8; border-radius: 4px;")
        self._warn.setVisible(False)
        root.addWidget(self._warn)

        # Summary
        self._summary = QLabel("")
        self._summary.setObjectName("subtitleLabel")
        self._summary.setVisible(False)
        root.addWidget(self._summary)

        # Output
        self._output = QTextEdit()
        self._output.setReadOnly(True)
        self._output.setPlaceholderText("Verbatim Pack output will appear here...")
        font = self._output.font()
        font.setFamily("Consolas")
        self._output.setFont(font)
        root.addWidget(self._output, 1)

        # Bottom buttons
        bottom = QHBoxLayout()
        self._copy_btn = QPushButton("Copy to Clipboard")
        self._copy_btn.setEnabled(False)
        self._copy_btn.clicked.connect(self._copy)
        bottom.addWidget(self._copy_btn)
        self._save_btn = QPushButton("Save as TXT")
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save)
        bottom.addWidget(self._save_btn)
        self._regen_btn = QPushButton("Regenerate")
        self._regen_btn.setEnabled(False)
        self._regen_btn.clicked.connect(self._generate)
        bottom.addWidget(self._regen_btn)
        bottom.addStretch()
        root.addLayout(bottom)

    def _add_files(self, paths: list):
        for p in paths:
            if p not in self._files:
                self._files.append(p)
                item = QListWidgetItem(os.path.basename(p))
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
                item.setData(Qt.UserRole, p)
                item.setToolTip(p)
                self._file_list.addItem(item)
        self._drop_zone.set_count(len(self._files))
        self._gen_btn.setEnabled(bool(self._files))

    def _browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select PDFs", "", "PDF Files (*.pdf)")
        if files:
            self._add_files(files)

    def _toggle_files_select(self):
        count = self._file_list.count()
        if count == 0:
            return
        all_checked = all(
            self._file_list.item(i).checkState() == Qt.Checked for i in range(count)
        )
        new_state = Qt.Unchecked if all_checked else Qt.Checked
        for i in range(count):
            self._file_list.item(i).setCheckState(new_state)
        self._files_select_btn.setText("\u2610 All" if not all_checked else "\u2611 All")

    def _remove_selected_files(self):
        to_remove = []
        for i in range(self._file_list.count()):
            item = self._file_list.item(i)
            if item and item.checkState() == Qt.Checked:
                to_remove.append(item.data(Qt.UserRole))
        if not to_remove:
            return
        for path in to_remove:
            if path in self._files:
                self._files.remove(path)
        self._file_list.clear()
        for p in self._files:
            item = QListWidgetItem(os.path.basename(p))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            item.setData(Qt.UserRole, p)
            item.setToolTip(p)
            self._file_list.addItem(item)
        self._drop_zone.set_count(len(self._files))
        self._gen_btn.setEnabled(bool(self._files))

    def _generate(self):
        if not self._files:
            return
        self._output.clear()
        self._pack_text = ""
        self._copy_btn.setEnabled(False)
        self._save_btn.setEnabled(False)
        self._regen_btn.setEnabled(False)
        self._gen_btn.setEnabled(False)
        self._vp_row.setVisible(False)
        self._warn.setVisible(False)
        self._summary.setVisible(False)
        self._progress.setValue(0)
        self._progress.setVisible(True)

        self._worker = ExtractionWorker(
            self._files, self._matter_edit.text().strip(),
            self._dol_edit.text().strip(),
        )
        self._worker.progress.connect(lambda c, t: (
            self._progress.setMaximum(t), self._progress.setValue(c)
        ))
        self._worker.status_msg.connect(lambda m: self._progress.setFormat(m))
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_finished(self, pack_text: str, summary: dict):
        self._pack_text = pack_text
        self._output.setPlainText(pack_text)
        self._progress.setVisible(False)
        self._gen_btn.setEnabled(True)
        self._copy_btn.setEnabled(True)
        self._save_btn.setEnabled(True)
        self._regen_btn.setEnabled(True)
        self._worker = None

        # VP status pills
        vp_pop = summary.get("vp_populated", {})
        missing = []
        for vp, lbl in self._vp_labels.items():
            if vp_pop.get(vp):
                lbl.setStyleSheet("padding: 4px 8px; border-radius: 8px; background: #1a3a1a; color: #a6e3a1;")
                lbl.setText(lbl.text().split(" ")[0] + " " + lbl.text().split(" ")[1] + " \u2713")
            else:
                lbl.setStyleSheet("padding: 4px 8px; border-radius: 8px; background: #3a1a1a; color: #f38ba8;")
                lbl.setText(lbl.text().split(" ")[0] + " " + lbl.text().split(" ")[1] + " \u2717")
                missing.append(f"{vp} ({VP_SECTIONS.get(vp, '')})")
        self._vp_row.setVisible(True)

        if missing:
            self._warn.setText("Missing: " + ", ".join(missing) + " \u2014 add relevant documents and regenerate")
            self._warn.setVisible(True)

        total = summary.get("total", 0)
        ai = summary.get("ai_count", 0)
        fb = summary.get("fallback_count", 0)
        self._summary.setText(f"{total} documents | {ai} AI-extracted | {fb} manual review")
        self._summary.setVisible(True)

    def _on_error(self, msg: str):
        self._progress.setVisible(False)
        self._gen_btn.setEnabled(True)
        QMessageBox.critical(self, "Extraction Error", msg)
        self._worker = None

    def _copy(self):
        if self._pack_text:
            QApplication.clipboard().setText(self._pack_text)

    def _save(self):
        if not self._pack_text:
            return
        matter = self._matter_edit.text().strip() or "VerbatimPack"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Verbatim Pack", f"{matter}_VerbatimPack.txt", "Text Files (*.txt)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._pack_text)

    # Drag and drop on tab itself
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        files = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".pdf"):
                files.append(path)
            elif os.path.isdir(path):
                for root, _, fns in os.walk(path):
                    for fn in fns:
                        if fn.lower().endswith(".pdf"):
                            files.append(os.path.join(root, fn))
        if files:
            self._add_files(files)
