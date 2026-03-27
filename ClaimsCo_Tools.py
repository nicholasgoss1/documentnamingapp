"""
ClaimsCo Document Tools — Combined Desktop App v1.0

Integrates:
  Tab 1 — Claim File Renamer   (existing functionality, preserved exactly)
  Tab 2 — Privacy Redactor     (PDF redaction using PyMuPDF)
  Tab 3 — PDF Extractor        (Master Evidence file generation for Claude)

Operator: ClaimsCo Pty Ltd
Run: python ClaimsCo_Tools.py
"""

import sys
import os
import re
import datetime
from collections import defaultdict

# ── Qt ───────────────────────────────────────────────────────────────────────
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QProgressBar, QTextEdit,
    QCheckBox, QFileDialog, QListWidget, QListWidgetItem,
    QGroupBox, QSplitter, QMessageBox, QStatusBar, QFrame,
    QGridLayout,
)

try:
    from PySide6.QtSvgWidgets import QSvgWidget
    _HAS_SVG = True
except ImportError:
    _HAS_SVG = False

# ── Ensure src/ package is importable (normal run AND PyInstaller frozen exe) ─
if getattr(sys, 'frozen', False):
    # PyInstaller extracts bundled files to sys._MEIPASS at runtime
    _BASE_DIR = sys._MEIPASS
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

from src.core.settings import Settings
from src.ui.main_window import MainWindow
from src.ui.theme import DARK_THEME, LIGHT_THEME

# ── Optional dependencies — import gracefully so app never crashes on missing ─
try:
    import fitz  # PyMuPDF — redaction + fallback extraction
    _HAS_FITZ = True
except ImportError:
    _HAS_FITZ = False

try:
    import pdfplumber
    _HAS_PDFPLUMBER = True
except ImportError:
    _HAS_PDFPLUMBER = False

_TESSERACT_EXE = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
_POPPLER_BIN   = r"C:\poppler\Library\bin"

try:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = _TESSERACT_EXE
    _HAS_TESSERACT = os.path.exists(_TESSERACT_EXE)
except ImportError:
    _HAS_TESSERACT = False

try:
    from pdf2image import convert_from_path
    _HAS_PDF2IMAGE = True
except ImportError:
    _HAS_PDF2IMAGE = False

try:
    from docx import Document as DocxDocument
    _HAS_DOCX = True
except ImportError:
    _HAS_DOCX = False

# File types the extractor handles
SUPPORTED_EXTENSIONS = (".pdf", ".txt", ".docx")

# ══════════════════════════════════════════════════════════════════════════════
# REDACTION PATTERNS
# Each entry: key -> (regex_pattern, human_label)
# ══════════════════════════════════════════════════════════════════════════════

REDACTION_PATTERNS = {
    "au_names": (
        r"\b[A-Z][a-z]{1,20}\s+[A-Z][a-z]{1,20}\b",
        "Australian Names",
    ),
    "au_mobile": (
        r"\b04\d{2}[\s\-]?\d{3}[\s\-]?\d{3}\b",
        "Mobile Numbers (04xx)",
    ),
    "au_landline": (
        r"\(0\d\)[\s\-]?\d{4}[\s\-]?\d{4}",
        "Landline Numbers",
    ),
    "au_address": (
        r"\b\d{1,4}\s+(?:[A-Z][a-z]+\s+){1,4}"
        r"(?:Street|St|Road|Rd|Avenue|Ave|Drive|Dr|Court|Ct|Place|Pl|"
        r"Way|Lane|Ln|Boulevard|Blvd|Terrace|Tce|Close|Cl|Circuit|Cct|"
        r"Crescent|Cres|Highway|Hwy|Parade|Pde)\b",
        "Street Addresses",
    ),
    "au_postcode": (
        r"\b(?:0[89]\d{2}|[1-9]\d{3})\b",
        "Postcodes",
    ),
    "email": (
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
        "Email Addresses",
    ),
    "tfn": (
        r"\b\d{3}[\s\-]?\d{3}[\s\-]?\d{3}\b",
        "Tax File Numbers (TFN)",
    ),
    "medicare": (
        r"\b[2-6]\d{3}[\s]?\d{5}[\s]?\d\b",
        "Medicare Numbers",
    ),
    "dob": (
        r"\b\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\b"
        r"|\b\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|"
        r"May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
        r"Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}\b",
        "Dates of Birth",
    ),
    "bsb": (
        r"\b\d{3}-\d{3}\b",
        "BSB Numbers",
    ),
    "bank_account": (
        r"\b[Aa](?:ccount)?[\s\-#:]*\d{6,10}\b",
        "Bank Account Numbers",
    ),
    "policy_number": (
        r"\b(?:POL|Policy|Pol\.?)[#\s\-]?\d{4,12}\b",
        "Policy Numbers",
    ),
    "claim_number": (
        r"\b(?:CLM|Claim|CL)[#\s\-]?\d{4,12}\b",
        "Claim Numbers",
    ),
}


# ══════════════════════════════════════════════════════════════════════════════
# EXTRACTION CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

# Filenames containing any of these substrings are excluded from extraction
INTERNAL_NOTES_KEYWORDS = [
    "claim notes history", "claim history notes", "timeline",
    "internal notes", "working notes", "claimsco notes",
]

# Filename substrings used to classify documents
COMPLAINANT_KEYWORDS = [
    "acb", "auscoast", "client", "complainant", "ruca", "weatherwatch",
    "hailtracker", "bom", "weather", "photos", "mudmap", "pds", "policy",
]
FF_KEYWORDS = [
    "insurer", "allianz", "qbe", "suncorp", "iag", "nrma", "aami",
    "cgu", "zurich", "hollard", "scope", "assessment", "denial",
    "decision", "preliminary",
]

SEPARATOR_LINE  = "─" * 62 + "\n"
WIDE_SEPARATOR  = "═" * 64
CHARS_PER_TOKEN = 4        # approximate Claude token size
CLAUDE_200K     = 200_000  # Claude 200K context window


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def classify_pdf(filename: str) -> str:
    """Return 'Complainant Document', 'FF Document', or 'Unknown — please classify manually'."""
    lower = filename.lower()
    if any(kw in lower for kw in COMPLAINANT_KEYWORDS):
        return "Complainant Document"
    if any(kw in lower for kw in FF_KEYWORDS):
        return "FF Document"
    return "Unknown — please classify manually"


def is_internal_notes(filename: str) -> bool:
    """Return True if the file should be excluded as internal notes."""
    lower = filename.lower()
    return any(kw in lower for kw in INTERNAL_NOTES_KEYWORDS)


def find_pattern_rects(page, pattern: str) -> list:
    """
    Find all bounding rectangles on a PDF page that match a regex pattern.

    Strategy:
      1. Extract words with their page coordinates via PyMuPDF.
      2. Group words by (block_no, line_no) to reconstruct lines.
      3. Run the compiled regex on each reconstructed line.
      4. For each match, union the bounding boxes of the covered words.

    Returns a list of fitz.Rect objects (one per match, possibly spanning
    multiple words on the same line).
    """
    rects = []
    try:
        # words = [(x0, y0, x1, y1, text, block_no, line_no, word_no), ...]
        words = page.get_text("words")
    except Exception:
        return rects

    if not words:
        return rects

    # Group by (block_no, line_no)
    lines: dict = defaultdict(list)
    for w in words:
        lines[(int(w[5]), int(w[6]))].append(w)

    compiled = re.compile(pattern, re.IGNORECASE)

    for line_words in lines.values():
        line_words.sort(key=lambda w: w[0])  # left to right

        line_text = ""
        spans: list = []  # (char_start, char_end, fitz.Rect)

        for w in line_words:
            x0, y0, x1, y1, text = w[0], w[1], w[2], w[3], w[4]
            start = len(line_text)
            end   = start + len(text)
            line_text += text + " "
            spans.append((start, end, fitz.Rect(x0, y0, x1, y1)))

        for match in compiled.finditer(line_text):
            ms, me = match.start(), match.end()
            hit_rects = [
                rect for (ws, we, rect) in spans
                if ws < me and we > ms
            ]
            if hit_rects:
                union = hit_rects[0]
                for r in hit_rects[1:]:
                    union = union | r
                rects.append(union)

    return rects


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — CLAIM FILE RENAMER
# ══════════════════════════════════════════════════════════════════════════════

class _CapturingStatusBar(QStatusBar):
    """
    QStatusBar subclass that emits a signal whenever showMessage is called.
    Used to forward Tab 1's internal status messages to the combined window's
    shared status bar without modifying the existing MainWindow source.
    """
    message_shown = Signal(str)

    def showMessage(self, message: str, timeout: int = 0):
        super().showMessage(message, timeout)
        self.message_shown.emit(message)


class RenamerTab(QWidget):
    """
    Tab 1: Embeds the existing Claim File Renamer (MainWindow) as an inline
    child widget.  All existing functionality — drag-drop, table editing,
    PDF preview, batch rename, undo, settings — is preserved exactly as-is.
    """

    status_message = Signal(str)

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)

        # Instantiate the existing MainWindow (do NOT call show())
        self._inner = MainWindow(settings)

        # Embed it as a plain child widget (removes top-level window chrome)
        self._inner.setParent(self)
        self._inner.setWindowFlags(Qt.Widget)

        # Replace its status bar with a capturing version so we can relay
        # messages to the outer combined window's shared status bar
        self._status_bar = _CapturingStatusBar()
        self._status_bar.message_shown.connect(self.status_message)
        self._inner.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready. Drag and drop PDF files to begin.")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._inner)

    def apply_theme(self, dark: bool):
        """Propagate theme changes to the embedded renamer window."""
        self._inner.setStyleSheet(DARK_THEME if dark else LIGHT_THEME)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — PRIVACY REDACTION  (background workers)
# ══════════════════════════════════════════════════════════════════════════════

class PreviewWorker(QThread):
    """
    Counts redaction instances across selected PDFs without modifying them.
    Runs in a background thread to keep the UI responsive.
    """
    finished = Signal(int, int)   # (total_instances, pages_scanned)
    log_line = Signal(str)

    def __init__(self, folder, files, patterns, custom_terms, parent=None):
        super().__init__(parent)
        self.folder       = folder
        self.files        = files
        self.patterns     = patterns      # {key: (regex, label)}
        self.custom_terms = custom_terms  # [str, ...]

    def run(self):
        if not _HAS_FITZ:
            self.log_line.emit("ERROR: PyMuPDF is not installed. Run: pip install PyMuPDF")
            self.finished.emit(0, 0)
            return

        total  = 0
        pages  = 0
        for filename in self.files:
            path = os.path.join(self.folder, filename)
            try:
                doc = fitz.open(path)
                for page in doc:
                    pages += 1
                    for _key, (pattern, _label) in self.patterns.items():
                        try:
                            total += len(find_pattern_rects(page, pattern))
                        except Exception:
                            pass
                    for term in self.custom_terms:
                        if term.strip():
                            try:
                                total += len(page.search_for(term.strip()))
                            except Exception:
                                pass
                doc.close()
            except Exception as e:
                self.log_line.emit(f"Warning: Could not scan {filename}: {e}")

        self.finished.emit(total, pages)


class RedactionWorker(QThread):
    """
    Redacts selected PDFs using PyMuPDF native redaction annotations.
    Each matched area is permanently removed from the text layer (not just
    painted over) via page.apply_redactions().
    Saves output to [folder]/Redacted/ — originals are never modified.
    """
    progress = Signal(int, int)   # (current, total)
    log_line = Signal(str)
    finished = Signal(dict)       # summary

    def __init__(self, folder, files, patterns, custom_terms,
                 add_watermark, parent=None):
        super().__init__(parent)
        self.folder        = folder
        self.files         = files
        self.patterns      = patterns
        self.custom_terms  = custom_terms
        self.add_watermark = add_watermark

    def run(self):
        if not _HAS_FITZ:
            self.log_line.emit(
                "ERROR: PyMuPDF is not installed. Run: pip install PyMuPDF")
            self.finished.emit({"total": 0, "success": 0, "failed": 0})
            return

        output_dir = os.path.join(self.folder, "Redacted")
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            self.log_line.emit(f"ERROR: Cannot create Redacted folder: {e}")
            self.finished.emit({"total": 0, "success": 0, "failed": 0})
            return

        log_entries = []
        success     = 0
        failed      = 0
        total       = len(self.files)

        for i, filename in enumerate(self.files):
            self.progress.emit(i + 1, total)
            src  = os.path.join(self.folder, filename)
            dst  = os.path.join(output_dir, filename)
            self.log_line.emit(f"\nProcessing: {filename}")

            try:
                doc              = fitz.open(src)
                total_redactions = 0
                categories_used  = set()
                pages_processed  = len(doc)

                for page in doc:
                    # ── Step 1: add redaction annotations ────────────────────
                    for _key, (pattern, label) in self.patterns.items():
                        try:
                            rects = find_pattern_rects(page, pattern)
                            for rect in rects:
                                page.add_redact_annot(rect, fill=(0, 0, 0))
                                total_redactions += 1
                                categories_used.add(label)
                        except Exception as err:
                            self.log_line.emit(
                                f"  Warning [{label}]: {err}")

                    for term in self.custom_terms:
                        if not term.strip():
                            continue
                        try:
                            hits = page.search_for(term.strip())
                            for rect in hits:
                                page.add_redact_annot(rect, fill=(0, 0, 0))
                                total_redactions += 1
                                categories_used.add("Custom Terms")
                        except Exception as err:
                            self.log_line.emit(
                                f"  Warning [custom '{term}']: {err}")

                    # ── Step 2: permanently apply redactions ──────────────────
                    page.apply_redactions()

                    # ── Step 3: optional watermark (added after redactions) ───
                    if self.add_watermark:
                        try:
                            wm_rect = fitz.Rect(
                                72,
                                page.rect.height - 30,
                                page.rect.width - 72,
                                page.rect.height - 10,
                            )
                            page.insert_textbox(
                                wm_rect,
                                "REDACTED — ClaimsCo",
                                fontsize=8,
                                color=(0.7, 0.7, 0.7),
                                align=fitz.TEXT_ALIGN_CENTER,
                            )
                        except Exception:
                            pass

                # Save the redacted copy (garbage=4 removes orphaned objects)
                doc.save(dst, garbage=4, deflate=True)
                doc.close()

                cat_list = ", ".join(sorted(categories_used)) or "None"
                self.log_line.emit(
                    f"  OK — {pages_processed} pages | "
                    f"{total_redactions} redactions | {cat_list}"
                )
                log_entries.append(
                    f"File: {filename}\n"
                    f"Pages processed: {pages_processed}\n"
                    f"Redactions applied: {total_redactions}\n"
                    f"Categories: {cat_list}\n"
                    f"{'-'*40}\n"
                )
                success += 1

            except Exception as e:
                self.log_line.emit(f"  ERROR: {e}")
                log_entries.append(
                    f"File: {filename}\n"
                    f"ERROR: {e}\n"
                    f"{'-'*40}\n"
                )
                failed += 1

        # Write redaction log to output folder
        log_path = os.path.join(output_dir, "redaction_log.txt")
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("ClaimsCo Redaction Log\n")
                f.write(
                    f"Generated: "
                    f"{datetime.datetime.now().strftime('%d %B %Y %H:%M')}\n"
                )
                f.write(f"Source folder: {self.folder}\n")
                f.write("=" * 60 + "\n\n")
                f.writelines(log_entries)
        except Exception as e:
            self.log_line.emit(f"Warning: Could not write redaction log: {e}")

        self.finished.emit({
            "total":      total,
            "success":    success,
            "failed":     failed,
            "output_dir": output_dir,
        })


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — PRIVACY REDACTION  (UI widget)
# ══════════════════════════════════════════════════════════════════════════════

class RedactionTab(QWidget):
    """
    Tab 2: Privacy Redaction.

    Lets users redact PII from PDFs before extraction.  Redacted copies are
    saved to [matter_folder]/Redacted/.  Original files are never touched.
    """

    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.folder   = ""
        self._worker  = None
        self._preview = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Privacy notice banner
        notice = QLabel(
            "Redacted files are saved locally. "
            "Original files are never modified. "
            "Verify redaction output before sharing any document externally."
        )
        notice.setWordWrap(True)
        notice.setStyleSheet(
            "padding: 8px; border: 1px solid #f38ba8; border-radius: 4px;"
        )
        root.addWidget(notice)

        # Folder picker row
        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel("Matter Folder:"))
        self._folder_label = QLabel("No folder selected")
        self._folder_label.setObjectName("subtitleLabel")
        browse_btn = QPushButton("Browse Folder...")
        browse_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(self._folder_label, 1)
        folder_row.addWidget(browse_btn)
        root.addLayout(folder_row)

        # Main horizontal splitter
        splitter = QSplitter(Qt.Horizontal)

        # ── Left pane: PDF file list ──────────────────────────────────────────
        left         = QWidget()
        left_layout  = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        files_group  = QGroupBox("PDFs in Folder")
        fg           = QVBoxLayout(files_group)

        sel_row = QHBoxLayout()
        self._select_all = QCheckBox("Select All")
        self._select_all.setChecked(True)
        self._select_all.toggled.connect(self._toggle_all_files)
        sel_row.addWidget(self._select_all)
        sel_row.addStretch()
        fg.addLayout(sel_row)

        self._file_list = QListWidget()
        self._file_list.setSelectionMode(QListWidget.NoSelection)
        fg.addWidget(self._file_list, 1)
        left_layout.addWidget(files_group, 1)
        splitter.addWidget(left)

        # ── Right pane: settings + log ────────────────────────────────────────
        right        = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Redaction rules grid
        rules_group = QGroupBox("Redaction Rules  (all on by default — uncheck to disable)")
        rules_grid  = QGridLayout(rules_group)
        rules_grid.setColumnStretch(0, 1)
        rules_grid.setColumnStretch(1, 1)
        self._rule_checks: dict = {}
        for idx, (key, (_pat, label)) in enumerate(REDACTION_PATTERNS.items()):
            cb = QCheckBox(label)
            cb.setChecked(True)
            self._rule_checks[key] = cb
            rules_grid.addWidget(cb, idx // 2, idx % 2)
        right_layout.addWidget(rules_group)

        # Custom terms
        custom_group = QGroupBox("Custom Terms to Redact  (one per line — exact match)")
        cg = QVBoxLayout(custom_group)
        self._custom_terms = QTextEdit()
        self._custom_terms.setPlaceholderText(
            "e.g.\nJohn Smith\nPOL-12345678\n04xx xxx xxx"
        )
        self._custom_terms.setFixedHeight(80)
        cg.addWidget(self._custom_terms)
        right_layout.addWidget(custom_group)

        # Watermark toggle
        self._watermark_cb = QCheckBox(
            "Add footer watermark to redacted files: 'REDACTED — ClaimsCo'"
        )
        right_layout.addWidget(self._watermark_cb)

        # Button row: preview + redact
        btn_row = QHBoxLayout()
        preview_btn = QPushButton("Preview Count")
        preview_btn.setToolTip(
            "Scan selected files and count how many instances would be redacted."
        )
        preview_btn.clicked.connect(self._run_preview)
        self._preview_label = QLabel("Not scanned yet.")
        redact_btn = QPushButton("Redact Selected Files")
        redact_btn.setObjectName("primaryButton")
        redact_btn.clicked.connect(self._run_redaction)
        btn_row.addWidget(preview_btn)
        btn_row.addWidget(self._preview_label, 1)
        btn_row.addWidget(redact_btn)
        right_layout.addLayout(btn_row)

        # Progress bar (hidden until running)
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        right_layout.addWidget(self._progress)

        # Log output
        log_group = QGroupBox("Redaction Log")
        lg = QVBoxLayout(log_group)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        lg.addWidget(self._log)
        right_layout.addWidget(log_group, 1)

        splitter.addWidget(right)
        splitter.setSizes([340, 660])
        root.addWidget(splitter, 1)

    # ── Folder / file management ──────────────────────────────────────────────

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Matter Folder", self.folder or ""
        )
        if not folder:
            return
        self.folder = folder
        self._folder_label.setText(folder)
        self._populate_file_list()
        self.status_message.emit(f"Folder loaded: {folder}")

    def _populate_file_list(self):
        self._file_list.clear()
        try:
            pdfs = sorted(
                f for f in os.listdir(self.folder)
                if f.lower().endswith(".pdf")
            )
        except Exception as e:
            self._log_append(f"ERROR reading folder: {e}")
            return

        if not pdfs:
            self._log_append("No PDF files found in this folder.")
            return

        for fn in pdfs:
            item = QListWidgetItem(fn)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self._file_list.addItem(item)

        self._log_append(f"Found {len(pdfs)} PDF(s) in folder.")

    def _toggle_all_files(self, checked: bool):
        state = Qt.Checked if checked else Qt.Unchecked
        for i in range(self._file_list.count()):
            self._file_list.item(i).setCheckState(state)

    def _selected_files(self) -> list:
        return [
            self._file_list.item(i).text()
            for i in range(self._file_list.count())
            if self._file_list.item(i).checkState() == Qt.Checked
        ]

    def _active_patterns(self) -> dict:
        return {
            key: REDACTION_PATTERNS[key]
            for key, cb in self._rule_checks.items()
            if cb.isChecked()
        }

    def _custom_term_list(self) -> list:
        return [
            line.strip()
            for line in self._custom_terms.toPlainText().splitlines()
            if line.strip()
        ]

    # ── Preview count ─────────────────────────────────────────────────────────

    def _run_preview(self):
        if not self.folder:
            QMessageBox.warning(self, "No Folder", "Select a folder first.")
            return
        files = self._selected_files()
        if not files:
            QMessageBox.warning(self, "No Files", "No files are checked.")
            return
        if not _HAS_FITZ:
            QMessageBox.critical(
                self, "Missing Dependency",
                "PyMuPDF is not installed.\nRun: pip install PyMuPDF"
            )
            return
        self._preview_label.setText("Scanning...")
        self._preview = PreviewWorker(
            self.folder, files, self._active_patterns(), self._custom_term_list()
        )
        self._preview.finished.connect(self._on_preview_done)
        self._preview.log_line.connect(self._log_append)
        self._preview.start()

    def _on_preview_done(self, total: int, pages: int):
        msg = f"{total:,} instances found across {pages} pages"
        self._preview_label.setText(msg)
        self.status_message.emit(msg)

    # ── Redaction ─────────────────────────────────────────────────────────────

    def _run_redaction(self):
        if not self.folder:
            QMessageBox.warning(self, "No Folder", "Select a folder first.")
            return
        files = self._selected_files()
        if not files:
            QMessageBox.warning(self, "No Files", "No files are checked.")
            return
        if not _HAS_FITZ:
            QMessageBox.critical(
                self, "Missing Dependency",
                "PyMuPDF is not installed.\nRun: pip install PyMuPDF"
            )
            return

        reply = QMessageBox.question(
            self, "Confirm Redaction",
            f"Redact {len(files)} file(s)?\n\n"
            "Redacted copies will be saved to a 'Redacted' subfolder.\n"
            "Original files will NOT be modified.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self._log.clear()
        self._progress.setMaximum(len(files))
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self.status_message.emit(f"Redacting {len(files)} file(s)...")

        self._worker = RedactionWorker(
            folder       = self.folder,
            files        = files,
            patterns     = self._active_patterns(),
            custom_terms = self._custom_term_list(),
            add_watermark= self._watermark_cb.isChecked(),
        )
        self._worker.progress.connect(
            lambda cur, _tot: self._progress.setValue(cur)
        )
        self._worker.log_line.connect(self._log_append)
        self._worker.finished.connect(self._on_redaction_done)
        self._worker.start()

    def _on_redaction_done(self, summary: dict):
        self._progress.setVisible(False)
        msg = (
            f"Redaction complete: {summary['success']} succeeded, "
            f"{summary['failed']} failed out of {summary['total']} file(s)."
        )
        self._log_append(f"\n{'='*60}\n{msg}")
        if summary.get("output_dir"):
            self._log_append(f"Output folder: {summary['output_dir']}")
        self.status_message.emit(msg)
        self._worker = None

    def _log_append(self, text: str):
        self._log.append(text)
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — PDF EXTRACTION  (background worker)
# ══════════════════════════════════════════════════════════════════════════════

class ExtractionWorker(QThread):
    """
    Extracts text from all non-skipped PDFs in a folder and writes a single
    structured Master Evidence TXT file formatted for Claude AFCA Assistant v24.

    Extraction strategy per page:
      1. pdfplumber (primary — best for text-layer PDFs)
      2. PyMuPDF  (fallback if pdfplumber fails or isn't installed)
      3. pytesseract OCR via pdf2image (fallback for pages with < 50 chars)
    """
    progress = Signal(int, int)       # (current, total_processable)
    log_line = Signal(str)
    finished = Signal(str, dict)      # (output_path, summary_dict)

    def __init__(self, folder: str, file_entries: list, parent=None):
        super().__init__(parent)
        self.folder       = folder
        # file_entries = [(filename, classification), ...]
        self.file_entries = file_entries

    def run(self):
        folder_name = os.path.basename(self.folder)
        output_path = os.path.join(
            self.folder, f"{folder_name}_MasterEvidence.txt"
        )

        # Windows-compatible date string (no leading zero on day)
        today   = datetime.date.today()
        day_str = str(today.day)  # int → str, naturally no leading zero
        date_str = today.strftime(f"{day_str} %B %Y")

        # Warn about missing optional dependencies
        if not _HAS_PDFPLUMBER:
            self.log_line.emit(
                "WARNING: pdfplumber not installed — "
                "text extraction may be limited. Run: pip install pdfplumber"
            )
        if not _HAS_TESSERACT:
            self.log_line.emit(
                f"WARNING: Tesseract OCR not found at {_TESSERACT_EXE}.\n"
                "Scanned PDFs will produce empty pages. Install from:\n"
                "https://github.com/UB-Mannheim/tesseract/wiki"
            )

        # ── Build file inventory ──────────────────────────────────────────────
        inventory_lines = [
            f"{'No.':<5} {'Filename':<55} {'Size':>7}  {'Classification'}\n",
            f"{'-'*100}\n",
        ]
        processable = []  # [(filename, classification), ...]

        for i, (fn, cls) in enumerate(self.file_entries, start=1):
            path = os.path.join(self.folder, fn)
            try:
                size_mb = os.path.getsize(path) / 1_048_576
            except Exception:
                size_mb = 0.0

            fn_display = (fn[:52] + "...") if len(fn) > 55 else fn

            if is_internal_notes(fn):
                inventory_lines.append(
                    f"{i:<5} {fn_display:<55} {size_mb:>6.2f}MB  "
                    f"SKIPPED (internal notes)\n"
                )
            else:
                inventory_lines.append(
                    f"{i:<5} {fn_display:<55} {size_mb:>6.2f}MB  {cls}\n"
                )
                processable.append((fn, cls))

        total_files = len(processable)
        total_pages = 0
        total_chars = 0
        content_blocks = []

        # ── Extract each processable file ─────────────────────────────────────
        for i, (fn, _cls) in enumerate(processable):
            self.progress.emit(i + 1, total_files)
            self.log_line.emit(f"\n[{i+1}/{total_files}] Extracting: {fn}")
            path = os.path.join(self.folder, fn)

            try:
                pages_text, method = self._extract_file(path)
            except Exception as e:
                self.log_line.emit(f"  ERROR: {e}")
                content_blocks.append(
                    f"[SOURCE: {fn} | PAGE: 1]\n"
                    f"[ERROR: Could not extract — {e}]\n"
                    + SEPARATOR_LINE
                )
                continue

            page_count = len(pages_text)
            file_chars = 0
            for page_num, text in enumerate(pages_text, start=1):
                text = (text or "").strip()
                content_blocks.append(
                    f"[SOURCE: {fn} | PAGE: {page_num}]\n"
                    f"{text}\n"
                    + SEPARATOR_LINE
                )
                file_chars += len(text)

            total_pages += page_count
            total_chars += file_chars
            self.log_line.emit(
                f"  OK — {page_count} pages | {file_chars:,} chars | {method}"
            )

        # ── Token estimates ───────────────────────────────────────────────────
        est_tokens = total_chars // CHARS_PER_TOKEN
        pct_200k   = (est_tokens / CLAUDE_200K) * 100

        # ── Assemble output file ──────────────────────────────────────────────
        header = (
            f"{WIDE_SEPARATOR}\n"
            f"CLAIMSCO PTY LTD — MASTER EVIDENCE FILE (v24-AWARE)\n"
            f"Matter folder: {folder_name}\n"
            f"Extracted: {date_str}\n"
            f"Prepared by: ClaimsCo PDF Extractor v1.0 (local Windows app)\n"
            f"For use with: Claude AFCA Assistant v24\n"
            f"{WIDE_SEPARATOR}\n\n"
            f"IMPORTANT — HOW TO USE THIS FILE WITH CLAUDE\n"
            f"{'─'*45}\n"
            f"1. Upload this TXT file to Claude AFCA Assistant v24.\n"
            f"2. Paste the intake prompt from Matter Extraction GPT v5.0.\n"
            f"3. Every passage is cited as [SOURCE: filename | PAGE: N].\n"
            f"4. Claude can quote verbatim and cite by page number.\n"
            f"5. Do not edit the [SOURCE] tags — they are used for citations.\n"
            f"{'='*64}\n\n"
        )

        inventory_block = "## FILE INVENTORY\n\n" + "".join(inventory_lines) + "\n"

        content_block = "## EXTRACTED CONTENT\n\n" + "".join(content_blocks)

        summary_block = (
            f"\n{'='*64}\n"
            f"## EXTRACTION SUMMARY\n"
            f"Total documents processed: {total_files}\n"
            f"Total pages extracted: {total_pages}\n"
            f"Total characters: {total_chars:,}\n"
            f"Estimated tokens: ~{est_tokens:,}\n"
            f"Claude 200K context used: ~{pct_200k:.1f}%\n"
        )
        if est_tokens > 150_000:
            summary_block += (
                "\nNOTE: Estimated tokens exceed 150,000. "
                "Consider splitting into two sessions:\n"
                "  Session 1: Complainant documents "
                "(PDS, expert reports, weather)\n"
                "  Session 2: FF documents "
                "(decision, scope, correspondence)\n"
            )

        full_output = header + inventory_block + content_block + summary_block

        # Write output file (UTF-8)
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(full_output)
            self.log_line.emit(f"\nOutput saved to: {output_path}")
        except Exception as e:
            self.log_line.emit(f"\nERROR saving output file: {e}")
            output_path = ""

        self.finished.emit(output_path, {
            "total_files": total_files,
            "total_pages": total_pages,
            "total_chars": total_chars,
            "est_tokens":  est_tokens,
            "pct_200k":    pct_200k,
        })

    # ── Extraction helpers ────────────────────────────────────────────────────

    def _extract_file(self, path: str):
        """
        Dispatch to the correct extractor based on file extension.
        Returns (list_of_page_text_strings, method_description).
        """
        ext = os.path.splitext(path)[1].lower()
        if ext == ".txt":
            return self._extract_txt(path)
        elif ext == ".docx":
            return self._extract_docx(path)
        else:
            return self._extract_pdf(path)

    def _extract_txt(self, path: str):
        """Read a plain-text file. Returns it as a single page."""
        encodings = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]
        for enc in encodings:
            try:
                with open(path, "r", encoding=enc) as f:
                    text = f.read()
                return [text], "txt"
            except (UnicodeDecodeError, LookupError):
                continue
        raise RuntimeError("Could not decode text file (tried utf-8, cp1252, latin-1).")

    def _extract_docx(self, path: str):
        """Extract text from a Word .docx file. Returns paragraphs as a single page."""
        if not _HAS_DOCX:
            raise RuntimeError(
                "python-docx is not installed. Run: pip install python-docx"
            )
        doc   = DocxDocument(path)
        lines = [para.text for para in doc.paragraphs if para.text.strip()]
        text  = "\n".join(lines)
        return [text], "docx"

    def _extract_pdf(self, path: str):
        """
        Extract text from all pages of a PDF.
        Returns (list_of_page_text_strings, method_description).
        Raises RuntimeError if all methods fail.
        """
        # ── Attempt 1: pdfplumber ─────────────────────────────────────────────
        if _HAS_PDFPLUMBER:
            try:
                pages  = []
                method = "pdfplumber"
                with pdfplumber.open(path) as pdf:
                    for idx, page in enumerate(pdf.pages):
                        try:
                            text = page.extract_text() or ""
                        except Exception:
                            text = ""
                        # If the page is sparse, try OCR
                        if len(text.strip()) < 50:
                            ocr = self._ocr_page(path, idx)
                            if len(ocr.strip()) > len(text.strip()):
                                text   = ocr
                                method = "ocr"
                        pages.append(text)
                return pages, method
            except Exception:
                pass  # fall through to PyMuPDF

        # ── Attempt 2: PyMuPDF ────────────────────────────────────────────────
        if _HAS_FITZ:
            try:
                pages  = []
                method = "pymupdf"
                doc    = fitz.open(path)
                for page in doc:
                    text = page.get_text("text") or ""
                    if len(text.strip()) < 50:
                        ocr = self._ocr_page(path, page.number)
                        if len(ocr.strip()) > len(text.strip()):
                            text   = ocr
                            method = "ocr"
                    pages.append(text)
                doc.close()
                return pages, method
            except Exception as e:
                raise RuntimeError(
                    f"PyMuPDF failed: {e}"
                ) from e

        raise RuntimeError(
            "No PDF library available. "
            "Install pdfplumber (pip install pdfplumber) or PyMuPDF."
        )

    def _ocr_page(self, path: str, page_index: int) -> str:
        """OCR a single page using pytesseract + pdf2image. Returns '' on failure."""
        if not (_HAS_TESSERACT and _HAS_PDF2IMAGE):
            return ""
        try:
            poppler = _POPPLER_BIN if os.path.isdir(_POPPLER_BIN) else None
            images  = convert_from_path(
                path,
                first_page  = page_index + 1,
                last_page   = page_index + 1,
                poppler_path= poppler,
            )
            if images:
                return pytesseract.image_to_string(images[0])
        except Exception:
            pass
        return ""


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — PDF EXTRACTION  (UI widget)
# ══════════════════════════════════════════════════════════════════════════════

class ExtractionTab(QWidget):
    """
    Tab 3: PDF Extractor.

    Extracts all PDFs in a matter folder (or a Redacted subfolder from Tab 2)
    into a single structured Master Evidence TXT file ready for upload to
    Claude AFCA Assistant v24.  Internal notes files are skipped automatically.
    """

    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.folder  = ""
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Folder picker
        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel("Matter Folder:"))
        self._folder_label = QLabel("No folder selected")
        self._folder_label.setObjectName("subtitleLabel")
        browse_btn = QPushButton("Browse Folder...")
        browse_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(self._folder_label, 1)
        folder_row.addWidget(browse_btn)
        root.addLayout(folder_row)

        # Dependency status line
        dep_items = []
        dep_items.append(
            "pdfplumber: OK" if _HAS_PDFPLUMBER else "pdfplumber: NOT INSTALLED"
        )
        dep_items.append(
            "python-docx: OK" if _HAS_DOCX else "python-docx: NOT INSTALLED"
        )
        dep_items.append(
            "Tesseract OCR: OK" if _HAS_TESSERACT
            else "Tesseract OCR: not found (OCR disabled)"
        )
        dep_items.append(
            "pdf2image: OK" if _HAS_PDF2IMAGE else "pdf2image: NOT INSTALLED"
        )
        dep_label = QLabel("  |  ".join(dep_items))
        dep_label.setObjectName("subtitleLabel")
        dep_label.setWordWrap(True)
        root.addWidget(dep_label)

        # Main splitter: file inventory left, log right
        splitter = QSplitter(Qt.Horizontal)

        # ── Left: inventory list ──────────────────────────────────────────────
        left = QWidget()
        ll   = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)

        inv_group = QGroupBox("PDF Inventory  (SKIP = excluded internal notes)")
        ig = QVBoxLayout(inv_group)
        self._file_list = QListWidget()
        self._file_list.setSelectionMode(QListWidget.NoSelection)
        ig.addWidget(self._file_list, 1)
        ll.addWidget(inv_group, 1)

        # Extract button + progress bar
        act_row = QHBoxLayout()
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        extract_btn = QPushButton("Extract PDFs")
        extract_btn.setObjectName("primaryButton")
        extract_btn.clicked.connect(self._run_extraction)
        act_row.addWidget(self._progress, 1)
        act_row.addWidget(extract_btn)
        ll.addLayout(act_row)
        splitter.addWidget(left)

        # ── Right: extraction log ─────────────────────────────────────────────
        right = QWidget()
        rl    = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        log_group = QGroupBox("Extraction Log")
        lg = QVBoxLayout(log_group)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        lg.addWidget(self._log, 1)
        rl.addWidget(log_group, 1)
        splitter.addWidget(right)

        splitter.setSizes([420, 580])
        root.addWidget(splitter, 1)

    # ── Folder / file management ──────────────────────────────────────────────

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Matter Folder", self.folder or ""
        )
        if not folder:
            return
        self.folder = folder
        self._folder_label.setText(folder)
        self._populate_inventory()
        self.status_message.emit(f"Extraction folder loaded: {folder}")

    def _populate_inventory(self):
        self._file_list.clear()
        try:
            files = sorted(
                f for f in os.listdir(self.folder)
                if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS
            )
        except Exception as e:
            self._log_append(f"ERROR reading folder: {e}")
            return

        if not files:
            self._log_append(
                "No supported files found (PDF, TXT, DOCX).")
            return

        skipped = 0
        for fn in files:
            path = os.path.join(self.folder, fn)
            try:
                size_mb = os.path.getsize(path) / 1_048_576
            except Exception:
                size_mb = 0.0

            if is_internal_notes(fn):
                label = f"[SKIP]  {fn}  ({size_mb:.2f} MB)"
                skipped += 1
            else:
                cls   = classify_pdf(fn)
                label = f"{fn}  ({size_mb:.2f} MB)  —  {cls}"

            self._file_list.addItem(QListWidgetItem(label))

        extract_count = len(files) - skipped
        self._log_append(
            f"Found {len(files)} file(s) (PDF/TXT/DOCX).  "
            f"{extract_count} to extract, {skipped} skipped (internal notes)."
        )

    # ── Extraction ────────────────────────────────────────────────────────────

    def _run_extraction(self):
        if not self.folder:
            QMessageBox.warning(self, "No Folder", "Select a folder first.")
            return

        try:
            all_files = sorted(
                f for f in os.listdir(self.folder)
                if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Cannot read folder:\n{e}")
            return

        if not all_files:
            QMessageBox.information(
                self, "No Files",
                "No supported files found (PDF, TXT, DOCX)."
            )
            return

        # Build (filename, classification) entries for all files
        # (the worker skips internal notes internally)
        file_entries = [(fn, classify_pdf(fn)) for fn in all_files]
        processable  = [
            fn for fn in all_files if not is_internal_notes(fn)
        ]

        if not processable:
            QMessageBox.information(
                self, "All Skipped",
                "All files in this folder are marked as internal notes "
                "and will be skipped."
            )
            return

        self._log.clear()
        self._log_append(
            f"Starting extraction: {len(processable)} file(s) to process."
        )
        self._progress.setMaximum(len(processable))
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self.status_message.emit(
            f"Extracting {len(processable)} PDF(s)..."
        )

        self._worker = ExtractionWorker(self.folder, file_entries)
        self._worker.progress.connect(
            lambda cur, _tot: self._progress.setValue(cur)
        )
        self._worker.log_line.connect(self._log_append)
        self._worker.finished.connect(self._on_extraction_done)
        self._worker.start()

    def _on_extraction_done(self, output_path: str, summary: dict):
        self._progress.setVisible(False)
        self._log_append(
            f"\n{'='*60}\n"
            f"EXTRACTION COMPLETE\n"
            f"Files processed : {summary['total_files']}\n"
            f"Pages extracted : {summary['total_pages']}\n"
            f"Characters      : {summary['total_chars']:,}\n"
            f"Estimated tokens: ~{summary['est_tokens']:,}\n"
            f"Claude 200K used: ~{summary['pct_200k']:.1f}%"
        )
        if output_path:
            self._log_append(f"\nOutput file: {output_path}")

        msg = (
            f"Extraction complete — {summary['total_pages']} pages, "
            f"~{summary['est_tokens']:,} tokens "
            f"({summary['pct_200k']:.1f}% of Claude 200K context)"
        )
        self.status_message.emit(msg)
        self._worker = None

    def _log_append(self, text: str):
        self._log.append(text)
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())


# ══════════════════════════════════════════════════════════════════════════════
# COMBINED MAIN WINDOW
# ══════════════════════════════════════════════════════════════════════════════

class CombinedMainWindow(QMainWindow):
    """
    Outer application window.

    Contains:
      - A common header bar showing the ClaimsCo logo / title
      - A QTabWidget with three tabs
      - A shared status bar at the bottom
      - A View menu for toggling dark/light mode (propagated to all tabs)
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ClaimsCo Document Tools")
        self.setMinimumSize(1280, 800)

        self._settings  = Settings()
        self._dark_mode = self._settings.get("dark_mode", True)

        self._build_menubar()
        self._build_ui()
        self._apply_theme()

        self.statusBar().showMessage("Ready.")

    # ── Menu bar ──────────────────────────────────────────────────────────────

    def _build_menubar(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")
        quit_act  = QAction("&Quit", self)
        quit_act.setShortcut("Ctrl+Q")
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        view_menu  = menubar.addMenu("&View")
        theme_act  = QAction("Toggle &Dark / Light Mode", self)
        theme_act.triggered.connect(self._toggle_theme)
        view_menu.addAction(theme_act)

    # ── Central UI ────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header bar ────────────────────────────────────────────────────────
        header = QWidget()
        header.setObjectName("appHeader")
        header.setFixedHeight(56)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 0, 16, 0)

        logo_path = os.path.join(_BASE_DIR, "assets", "claimsco_logo.svg")
        if _HAS_SVG and os.path.exists(logo_path):
            logo = QSvgWidget(logo_path)
            logo.setFixedSize(160, 44)
            hl.addWidget(logo)
        else:
            brand = QLabel("ClaimsCo")
            brand.setObjectName("titleLabel")
            hl.addWidget(brand)

        hl.addSpacing(12)
        subtitle = QLabel("Document Tools")
        subtitle.setObjectName("titleLabel")
        hl.addWidget(subtitle)
        hl.addStretch()

        root.addWidget(header)

        # Thin separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        root.addWidget(sep)

        # ── Tab widget ────────────────────────────────────────────────────────
        self._tabs = QTabWidget()

        # Tab 1 — Claim File Renamer (existing functionality)
        self._renamer_tab = RenamerTab(self._settings)
        self._renamer_tab.status_message.connect(self.statusBar().showMessage)
        self._tabs.addTab(self._renamer_tab, "Document Renaming")

        # Tab 2 — Privacy Redaction
        self._redaction_tab = RedactionTab()
        self._redaction_tab.status_message.connect(self.statusBar().showMessage)
        self._tabs.addTab(self._redaction_tab, "Privacy Redaction")

        # Tab 3 — PDF Extraction
        self._extraction_tab = ExtractionTab()
        self._extraction_tab.status_message.connect(self.statusBar().showMessage)
        self._tabs.addTab(self._extraction_tab, "PDF Extraction")

        root.addWidget(self._tabs, 1)

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _apply_theme(self):
        sheet = DARK_THEME if self._dark_mode else LIGHT_THEME
        self.setStyleSheet(sheet)
        # Propagate to the embedded renamer window so its own stylesheet
        # matches when the user switches modes
        self._renamer_tab.apply_theme(self._dark_mode)

    def _toggle_theme(self):
        self._dark_mode = not self._dark_mode
        self._settings.set("dark_mode", self._dark_mode)
        self._apply_theme()


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    # Enable high-DPI scaling on Windows 10/11
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("ClaimsCo Document Tools")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("ClaimsCo")

    icon_path = os.path.join(_BASE_DIR, "assets", "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = CombinedMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
