"""
Privacy Redaction tab - scans PDFs for PII and replaces with tokens.
"""
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import fitz  # PyMuPDF

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QProgressBar, QTableWidget, QTableWidgetItem,
    QFileDialog, QDialog, QTextEdit, QHeaderView, QGroupBox,
    QMessageBox,
)

# ---------------------------------------------------------------------------
# Optional spaCy support
# ---------------------------------------------------------------------------
_HAS_SPACY = False
_NLP = None
try:
    import spacy
    _NLP = spacy.load("en_core_web_sm")
    _HAS_SPACY = True
except Exception:
    pass

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------
_RE_PHONE = re.compile(
    r'\b(?:04\d{2}[\s-]?\d{3}[\s-]?\d{3}|(?:\(0\d\)|0\d)[\s-]?\d{4}[\s-]?\d{4})\b'
)
_RE_POLICY = re.compile(r'\b[A-Z]{2,4}[-]?\d{6,12}\b')
_RE_ADDRESS = re.compile(
    r'\b\d{1,5}\s+[A-Z][a-z]+\s+'
    r'(?:Street|St|Road|Rd|Avenue|Ave|Drive|Dr|Court|Ct|Place|Pl|Lane|Ln|'
    r'Crescent|Cres|Way|Boulevard|Blvd|Terrace|Tce|Circuit|Cct|Close|Cl|'
    r'Parade|Pde|Highway|Hwy)\b'
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class FileResult:
    filename: str
    lines_processed: int = 0
    pii_tokens_found: int = 0
    status: str = "Pending"
    redacted_lines: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Worker thread
# ---------------------------------------------------------------------------
class RedactionWorker(QThread):
    """Background worker that scans PDFs and redacts PII."""

    progress = Signal(int, int)          # current file index, total files
    file_done = Signal(int, object)      # file index, FileResult
    finished = Signal(list, dict)        # List[FileResult], token_map
    error = Signal(str)

    def __init__(
        self,
        folder: str,
        firm_name: str,
        matter_ref: str,
        parent=None,
    ):
        super().__init__(parent)
        self._folder = folder
        self._firm_name = firm_name
        self._matter_ref = matter_ref

    # ---- internal helpers ------------------------------------------------

    @staticmethod
    def _extract_text(path: str) -> List[str]:
        doc = fitz.open(path)
        lines: List[str] = []
        for page in doc:
            text = page.get_text("text")
            lines.extend(text.splitlines())
        doc.close()
        return lines

    def _find_pii_spans(self, line: str) -> List[Tuple[int, int, str]]:
        """Return sorted, non-overlapping (start, end, matched_text) spans."""
        spans: List[Tuple[int, int, str]] = []

        # spaCy NER - PERSON entities with 2+ words
        if _HAS_SPACY and _NLP is not None:
            doc = _NLP(line)
            for ent in doc.ents:
                if ent.label_ == "PERSON" and len(ent.text.split()) >= 2:
                    spans.append((ent.start_char, ent.end_char, ent.text))

        # Regex patterns
        for m in _RE_ADDRESS.finditer(line):
            spans.append((m.start(), m.end(), m.group()))
        for m in _RE_PHONE.finditer(line):
            spans.append((m.start(), m.end(), m.group()))
        for m in _RE_POLICY.finditer(line):
            spans.append((m.start(), m.end(), m.group()))

        # Sort by start position, then remove overlaps (keep longer match)
        spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
        merged: List[Tuple[int, int, str]] = []
        for span in spans:
            if merged and span[0] < merged[-1][1]:
                continue  # overlaps with previous - skip
            merged.append(span)
        return merged

    def _redact_line(
        self,
        line: str,
        token_map: Dict[str, str],
        reverse_map: Dict[str, str],
        counter: List[int],
    ) -> Tuple[str, int]:
        """Replace PII in *line* with tokens.  Returns (redacted_line, n_new_tokens)."""
        spans = self._find_pii_spans(line)
        if not spans:
            return line, 0

        new_tokens = 0
        parts: List[str] = []
        prev_end = 0
        for start, end, value in spans:
            parts.append(line[prev_end:start])
            normalised = value.strip()
            if normalised in reverse_map:
                token = reverse_map[normalised]
            else:
                counter[0] += 1
                token = f"[CLIENT_ID_{counter[0]:03d}]"
                token_map[token] = normalised
                reverse_map[normalised] = token
                new_tokens += 1
            parts.append(token)
            prev_end = end
        parts.append(line[prev_end:])
        return "".join(parts), new_tokens

    # ---- main run --------------------------------------------------------

    def run(self):
        try:
            pdf_files = sorted(
                f for f in os.listdir(self._folder)
                if f.lower().endswith(".pdf")
            )
            if not pdf_files:
                self.error.emit("No PDF files found in the selected folder.")
                return

            total = len(pdf_files)
            token_map: Dict[str, str] = {}      # token -> real value
            reverse_map: Dict[str, str] = {}    # real value -> token
            counter = [0]                        # mutable int wrapper
            results: List[FileResult] = []

            for idx, filename in enumerate(pdf_files):
                self.progress.emit(idx, total)
                path = os.path.join(self._folder, filename)
                result = FileResult(filename=filename)
                try:
                    lines = self._extract_text(path)
                    result.lines_processed = len(lines)
                    pii_count = 0
                    for line in lines:
                        redacted, n = self._redact_line(
                            line, token_map, reverse_map, counter
                        )
                        pii_count += n
                        result.redacted_lines.append(redacted)
                    result.pii_tokens_found = pii_count
                    result.status = "Done"
                except Exception as exc:
                    result.status = f"Error: {exc}"
                results.append(result)
                self.file_done.emit(idx, result)

            self.progress.emit(total, total)
            self.finished.emit(results, token_map)
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Token Map dialog
# ---------------------------------------------------------------------------
class TokenMapDialog(QDialog):
    """Read-only dialog showing the full token-to-real-value mapping."""

    def __init__(self, token_map: Dict[str, str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Token Map")
        self.setMinimumSize(520, 400)

        layout = QVBoxLayout(self)

        title = QLabel("PII Token Map")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        subtitle = QLabel(
            "Each token below maps to the original PII value that was redacted."
        )
        subtitle.setObjectName("subtitleLabel")
        layout.addWidget(subtitle)

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        lines: List[str] = []
        for token, value in token_map.items():
            lines.append(f"{token}  \u2192  {value}")
        text_edit.setPlainText("\n".join(lines) if lines else "(no tokens)")
        layout.addWidget(text_edit)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)


# ---------------------------------------------------------------------------
# Privacy Redaction tab widget
# ---------------------------------------------------------------------------
class PrivacyTab(QWidget):
    """Tab 2 - Privacy Redaction for insurance claim PDFs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: RedactionWorker | None = None
        self._results: List[FileResult] = []
        self._token_map: Dict[str, str] = {}
        self._build_ui()

    # ---- UI construction -------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Title
        title = QLabel("Privacy Redaction")
        title.setObjectName("titleLabel")
        root.addWidget(title)

        subtitle = QLabel(
            "Scan a folder of PDFs for personally identifiable information and "
            "replace with anonymised tokens."
        )
        subtitle.setObjectName("subtitleLabel")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        # --- Input group ---
        input_group = QGroupBox("Scan Settings")
        input_layout = QVBoxLayout(input_group)

        # Folder row
        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel("Folder:"))
        self._folder_edit = QLineEdit()
        self._folder_edit.setPlaceholderText("Select folder containing PDFs...")
        folder_row.addWidget(self._folder_edit, 1)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(browse_btn)
        input_layout.addLayout(folder_row)

        # Firm name row
        firm_row = QHBoxLayout()
        firm_row.addWidget(QLabel("Firm Name:"))
        self._firm_edit = QLineEdit("ClaimsCo Pty Ltd")
        firm_row.addWidget(self._firm_edit, 1)
        input_layout.addLayout(firm_row)

        # Matter reference row
        matter_row = QHBoxLayout()
        matter_row.addWidget(QLabel("Matter Ref:"))
        self._matter_edit = QLineEdit()
        self._matter_edit.setPlaceholderText("e.g. MAT-2026-0042")
        matter_row.addWidget(self._matter_edit, 1)
        input_layout.addLayout(matter_row)

        root.addWidget(input_group)

        # --- Action row ---
        action_row = QHBoxLayout()
        self._scan_btn = QPushButton("Scan && Redact All PDFs")
        self._scan_btn.setObjectName("primaryButton")
        self._scan_btn.clicked.connect(self._start_scan)
        action_row.addWidget(self._scan_btn)
        action_row.addStretch()
        root.addLayout(action_row)

        # --- Progress bar ---
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setTextVisible(True)
        root.addWidget(self._progress)

        # --- Stats row ---
        stats_row = QHBoxLayout()
        self._lbl_total_docs = QLabel("Documents: 0")
        self._lbl_total_lines = QLabel("Total Lines: 0")
        self._lbl_total_pii = QLabel("PII Tokens Found: 0")
        for lbl in (self._lbl_total_docs, self._lbl_total_lines, self._lbl_total_pii):
            lbl.setObjectName("subtitleLabel")
            stats_row.addWidget(lbl)
        stats_row.addStretch()
        root.addLayout(stats_row)

        # --- Results table ---
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels([
            "Filename", "Lines Processed", "PII Tokens Created", "Status"
        ])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        for col in (1, 2):
            self._table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents
            )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        root.addWidget(self._table, 1)

        # --- Bottom buttons ---
        bottom_row = QHBoxLayout()
        self._download_btn = QPushButton("Download Redacted Pack (.txt)")
        self._download_btn.setEnabled(False)
        self._download_btn.clicked.connect(self._download_pack)
        bottom_row.addWidget(self._download_btn)

        self._view_map_btn = QPushButton("View Token Map")
        self._view_map_btn.setEnabled(False)
        self._view_map_btn.clicked.connect(self._view_token_map)
        bottom_row.addWidget(self._view_map_btn)

        bottom_row.addStretch()
        root.addLayout(bottom_row)

    # ---- Slots -----------------------------------------------------------

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select PDF Folder", self._folder_edit.text()
        )
        if folder:
            self._folder_edit.setText(folder)

    def _start_scan(self):
        folder = self._folder_edit.text().strip()
        if not folder or not os.path.isdir(folder):
            QMessageBox.warning(
                self, "Invalid Folder",
                "Please select a valid folder containing PDF files."
            )
            return

        # Reset state
        self._results.clear()
        self._token_map.clear()
        self._table.setRowCount(0)
        self._update_stats()
        self._download_btn.setEnabled(False)
        self._view_map_btn.setEnabled(False)
        self._scan_btn.setEnabled(False)

        self._progress.setValue(0)
        self._progress.setVisible(True)

        self._worker = RedactionWorker(
            folder=folder,
            firm_name=self._firm_edit.text().strip(),
            matter_ref=self._matter_edit.text().strip(),
            parent=self,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.file_done.connect(self._on_file_done)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, current: int, total: int):
        self._progress.setMaximum(total)
        self._progress.setValue(current)
        self._progress.setFormat(f"Processing {current}/{total} files...")

    def _on_file_done(self, index: int, result: FileResult):
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(result.filename))
        self._table.setItem(
            row, 1, QTableWidgetItem(str(result.lines_processed))
        )
        self._table.setItem(
            row, 2, QTableWidgetItem(str(result.pii_tokens_found))
        )
        self._table.setItem(row, 3, QTableWidgetItem(result.status))

        # Right-align numeric columns
        for col in (1, 2):
            item = self._table.item(row, col)
            if item:
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )

    def _on_finished(self, results: List[FileResult], token_map: Dict[str, str]):
        self._results = results
        self._token_map = token_map
        self._progress.setValue(self._progress.maximum())
        self._progress.setFormat("Complete")
        self._scan_btn.setEnabled(True)
        self._download_btn.setEnabled(True)
        self._view_map_btn.setEnabled(bool(token_map))
        self._update_stats()
        self._worker = None

    def _on_error(self, message: str):
        self._progress.setVisible(False)
        self._scan_btn.setEnabled(True)
        QMessageBox.critical(self, "Redaction Error", message)
        self._worker = None

    def _update_stats(self):
        total_docs = len(self._results)
        total_lines = sum(r.lines_processed for r in self._results)
        total_pii = sum(r.pii_tokens_found for r in self._results)
        self._lbl_total_docs.setText(f"Documents: {total_docs}")
        self._lbl_total_lines.setText(f"Total Lines: {total_lines}")
        self._lbl_total_pii.setText(f"PII Tokens Found: {total_pii}")

    def _download_pack(self):
        if not self._results:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Redacted Pack",
            "redacted_pack.txt",
            "Text Files (*.txt)",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                for result in self._results:
                    for line in result.redacted_lines:
                        fh.write(f"[{result.filename}] {line}\n")
            QMessageBox.information(
                self, "Export Complete",
                f"Redacted pack saved to:\n{path}"
            )
        except Exception as exc:
            QMessageBox.critical(
                self, "Export Error", f"Failed to save file:\n{exc}"
            )

    def _view_token_map(self):
        dlg = TokenMapDialog(self._token_map, parent=self)
        dlg.exec()
