"""
Privacy Redaction tab — PDF viewer with auto + manual redaction tools.
"""
import os
import re
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import fitz  # PyMuPDF

from PySide6.QtCore import Qt, Signal, QThread, QRect, QPoint, QRectF, QSize, QTimer
from PySide6.QtGui import (
    QPixmap, QImage, QPainter, QColor, QPen, QBrush, QCursor, QDragEnterEvent, QDropEvent,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QListWidget, QListWidgetItem, QScrollArea, QSplitter, QFileDialog,
    QMessageBox, QGroupBox, QApplication, QRubberBand, QFrame, QToolButton,
)

logger = logging.getLogger(__name__)

# ── spaCy loading (works in both dev and PyInstaller bundle) ──
_HAS_SPACY = False
_NLP = None


def _load_spacy_model():
    try:
        import spacy
        import sys
        from pathlib import Path
        # Try bundled path first (PyInstaller)
        base = getattr(sys, '_MEIPASS', None)
        if base:
            model_path = Path(base) / "en_core_web_sm"
            if model_path.exists():
                return spacy.load(str(model_path))
        # Try installed model
        return spacy.load("en_core_web_sm")
    except Exception as e:
        logger.debug("spaCy load failed: %s", e)
        return None


_NLP = _load_spacy_model()
_HAS_SPACY = _NLP is not None

# ── Regex patterns for PII detection ──
_RE_PHONE = re.compile(r'(\+?61[\s-]?)?(0\d[\s-]?)[\d\s-]{8,10}')
_RE_POLICY = re.compile(r'\b[A-Z]{2,4}[-]?\d{6,12}\b')
_RE_ACCOUNT = re.compile(r'\d{12,}')

# Street number: handles "17A", "4/17", "Unit 3", etc.
_RE_STREET = re.compile(
    r'\b(?:Unit\s+|Lot\s+|Suite\s+|Level\s+)?'
    r'(\d{1,4}[A-Za-z]?(?:/\d{1,4})?)'
    r'\b(?=\s+[A-Z][a-z]+'
    r'\s+(?:Street|St|Road|Rd|Avenue|Ave|Drive|Dr|'
    r'Court|Ct|Place|Pl|Crescent|Cres|Boulevard|Blvd|'
    r'Lane|Ln|Way|Terrace|Tce|Close|Cl|Highway|Hwy|'
    r'Parade|Pde|Circuit|Cct|Grove|Gve))'
)

# Full Australian address: "17A Railway Street, Gatton QLD 4343"
_RE_ADDRESS = re.compile(
    r'\b\d{1,4}[A-Za-z]?\s+'
    r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s*,?\s*'
    r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+'
    r'(?:QLD|NSW|VIC|WA|SA|TAS|ACT|NT)\s+'
    r'\d{4}\b'
)

# Label-value pairs: "Name: Craig Toohill", "Address: 17A Railway St"
_RE_LABEL_VALUE = re.compile(
    r'^(?:Name|Address|Client|Insured(?:\s+Name)?|'
    r'Customer|Owner|Claimant|Policy\s*Holder|'
    r'Insured\s*Name|Report\s*For|Prepared\s*For)'
    r'\s*:?\s*(.+)$',
    re.MULTILINE | re.IGNORECASE
)

# Reference numbers near labels
_RE_REF_LABEL = re.compile(
    r'(?:Job\s*(?:Number|No|#)|Claim\s*(?:Number|No|#)|'
    r'Reference|Ref\s*(?:No|#)|Policy\s*(?:Number|No))'
    r'\s*:?\s*([A-Z0-9]{4,20}(?:[-/][A-Z0-9]+)?)',
    re.IGNORECASE
)

# Default DPI for rendering
_DEFAULT_DPI = 150
_MIN_DPI = 72
_MAX_DPI = 300


@dataclass
class RedactionBox:
    page_num: int
    pdf_rect: tuple  # (x0, y0, x1, y1) in PDF coordinates
    type: str  # "AUTO" or "MANUAL"
    text: str = ""  # detected text or ""


class DropZone(QFrame):
    """Dashed-border drop zone that accepts PDFs and folders."""
    files_dropped = Signal(list)
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(120)
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
        self._count_label = QLabel("")
        self._count_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._count_label)

    def set_count(self, n: int):
        self._count_label.setText(f"{n} files loaded" if n else "")

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


class AutoRedactWorker(QThread):
    """Background worker for auto-detecting PII in PDFs."""
    progress = Signal(int, int)  # current_page, total_pages
    page_done = Signal(int, list)  # page_num, list of RedactionBox
    finished = Signal(dict)  # summary: {names, addresses, phones, refs, total}

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self._file_path = file_path

    def _search_and_add(self, page, page_num, pii_text, boxes, seen_rects):
        """Search for PII text on page and add non-overlapping boxes."""
        try:
            rects = page.search_for(pii_text.strip())
            for r in rects:
                key = (page_num, round(r.x0, 1), round(r.y0, 1), round(r.x1, 1), round(r.y1, 1))
                if key not in seen_rects:
                    seen_rects.add(key)
                    boxes.append(RedactionBox(
                        page_num=page_num,
                        pdf_rect=(r.x0, r.y0, r.x1, r.y1),
                        type="AUTO",
                        text=pii_text.strip(),
                    ))
        except Exception:
            pass

    def run(self):
        counts = {"names": 0, "addresses": 0, "phones": 0, "refs": 0, "total": 0}
        try:
            doc = fitz.open(self._file_path)
            total = len(doc)
            for page_num in range(total):
                self.progress.emit(page_num + 1, total)
                page = doc[page_num]
                text = page.get_text()
                boxes = []
                seen = set()  # dedup rects

                # 1. spaCy PERSON entities (most reliable for names)
                if _HAS_SPACY and _NLP:
                    try:
                        nlp_doc = _NLP(text)
                        for ent in nlp_doc.ents:
                            if ent.label_ == "PERSON" and len(ent.text.split()) >= 2:
                                before = len(boxes)
                                self._search_and_add(page, page_num, ent.text, boxes, seen)
                                counts["names"] += len(boxes) - before
                    except Exception:
                        pass

                # 2. Label-value pairs (Name: Craig Toohill, Address: ...)
                try:
                    for m in _RE_LABEL_VALUE.finditer(text):
                        value = m.group(1).strip()
                        if len(value) >= 3:
                            before = len(boxes)
                            self._search_and_add(page, page_num, value, boxes, seen)
                            counts["names"] += len(boxes) - before
                except Exception:
                    pass

                # 3. Full address pattern
                try:
                    for m in _RE_ADDRESS.finditer(text):
                        before = len(boxes)
                        self._search_and_add(page, page_num, m.group(), boxes, seen)
                        counts["addresses"] += len(boxes) - before
                except Exception:
                    pass

                # 4. Street number pattern
                try:
                    for m in _RE_STREET.finditer(text):
                        before = len(boxes)
                        self._search_and_add(page, page_num, m.group(), boxes, seen)
                        counts["addresses"] += len(boxes) - before
                except Exception:
                    pass

                # 5. Phone numbers
                try:
                    for m in _RE_PHONE.finditer(text):
                        matched = m.group().strip()
                        if len(matched) >= 8:
                            before = len(boxes)
                            self._search_and_add(page, page_num, matched, boxes, seen)
                            counts["phones"] += len(boxes) - before
                except Exception:
                    pass

                # 6. Policy/claim numbers
                try:
                    for m in _RE_POLICY.finditer(text):
                        before = len(boxes)
                        self._search_and_add(page, page_num, m.group(), boxes, seen)
                        counts["refs"] += len(boxes) - before
                except Exception:
                    pass

                # 7. Reference numbers near labels
                try:
                    for m in _RE_REF_LABEL.finditer(text):
                        ref = m.group(1).strip()
                        if len(ref) >= 4:
                            before = len(boxes)
                            self._search_and_add(page, page_num, ref, boxes, seen)
                            counts["refs"] += len(boxes) - before
                except Exception:
                    pass

                # 8. Account numbers
                try:
                    for m in _RE_ACCOUNT.finditer(text):
                        before = len(boxes)
                        self._search_and_add(page, page_num, m.group(), boxes, seen)
                        counts["refs"] += len(boxes) - before
                except Exception:
                    pass

                self.page_done.emit(page_num, boxes)
            doc.close()
        except Exception as e:
            logger.debug("Auto-redact error: %s", e)
        counts["total"] = counts["names"] + counts["addresses"] + counts["phones"] + counts["refs"]
        self.finished.emit(counts)


class PageWidget(QLabel):
    """Renders one page of a PDF with redaction overlay boxes."""
    box_drawn = Signal(int, tuple)  # page_num, (x0, y0, x1, y1) in PDF coords
    box_clicked = Signal(int, QPoint)  # page_num, click point in PDF coords

    def __init__(self, page_num: int, parent=None):
        super().__init__(parent)
        self.page_num = page_num
        self._pixmap: Optional[QPixmap] = None
        self._boxes: List[RedactionBox] = []
        self._dpi_scale = _DEFAULT_DPI / 72.0
        self._drawing = False
        self._erasing = False
        self._rubber_band: Optional[QRubberBand] = None
        self._drag_start = QPoint()

    def set_pixmap(self, pixmap: QPixmap, dpi_scale: float):
        self._pixmap = pixmap
        self._dpi_scale = dpi_scale
        self._redraw()

    def set_boxes(self, boxes: List[RedactionBox]):
        self._boxes = boxes
        self._redraw()

    def set_drawing_mode(self, on: bool):
        self._drawing = on
        self._erasing = False
        self.setCursor(Qt.CrossCursor if on else Qt.ArrowCursor)

    def set_erasing_mode(self, on: bool):
        self._erasing = on
        self._drawing = False
        self.setCursor(Qt.PointingHandCursor if on else Qt.ArrowCursor)

    def _redraw(self):
        if not self._pixmap:
            return
        canvas = QPixmap(self._pixmap)
        painter = QPainter(canvas)
        for box in self._boxes:
            if box.page_num != self.page_num:
                continue
            x0, y0, x1, y1 = box.pdf_rect
            s = self._dpi_scale
            rect = QRectF(x0 * s, y0 * s, (x1 - x0) * s, (y1 - y0) * s)
            if box.type == "AUTO":
                painter.fillRect(rect, QColor(255, 0, 0, 120))
            else:
                painter.fillRect(rect, QColor(0, 0, 0, 255))
        painter.end()
        super().setPixmap(canvas)

    def mousePressEvent(self, event):
        if self._drawing and event.button() == Qt.LeftButton:
            self._drag_start = event.pos()
            self._rubber_band = QRubberBand(QRubberBand.Rectangle, self)
            self._rubber_band.setGeometry(QRect(self._drag_start, QSize()))
            self._rubber_band.show()
        elif self._erasing and event.button() == Qt.LeftButton:
            # Convert click to PDF coords
            s = self._dpi_scale
            px, py = event.pos().x() / s, event.pos().y() / s
            self.box_clicked.emit(self.page_num, QPoint(int(px * 100), int(py * 100)))
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._rubber_band:
            self._rubber_band.setGeometry(
                QRect(self._drag_start, event.pos()).normalized()
            )

    def mouseReleaseEvent(self, event):
        if self._rubber_band:
            rect = self._rubber_band.geometry()
            self._rubber_band.hide()
            self._rubber_band = None
            if rect.width() > 5 and rect.height() > 5:
                s = self._dpi_scale
                pdf_rect = (
                    rect.x() / s, rect.y() / s,
                    (rect.x() + rect.width()) / s,
                    (rect.y() + rect.height()) / s,
                )
                self.box_drawn.emit(self.page_num, pdf_rect)


class SaveWorker(QThread):
    """Saves redacted PDFs in background."""
    progress = Signal(int, int)
    finished = Signal(int, str)  # count_saved, output_folder

    def __init__(self, files_and_boxes: list, output_folder: str, parent=None):
        super().__init__(parent)
        self._items = files_and_boxes  # [(filepath, [RedactionBox])]
        self._output_folder = output_folder

    def run(self):
        total = len(self._items)
        saved = 0
        for idx, (filepath, boxes) in enumerate(self._items):
            self.progress.emit(idx + 1, total)
            try:
                doc = fitz.open(filepath)
                for box in boxes:
                    page = doc[box.page_num]
                    r = fitz.Rect(*box.pdf_rect)
                    page.add_redact_annot(r)
                for page in doc:
                    page.apply_redactions()
                stem = os.path.splitext(os.path.basename(filepath))[0]
                out_path = os.path.join(self._output_folder, f"{stem}_REDACTED.pdf")
                doc.save(out_path, garbage=4, deflate=True)
                doc.close()
                saved += 1
            except Exception as e:
                logger.debug("Save redaction error for %s: %s", filepath, e)
        self.finished.emit(saved, self._output_folder)


class PrivacyTab(QWidget):
    """Tab 2 — Privacy Redaction with PDF viewer and redaction tools."""

    # Signal to send files to Tab 3
    send_to_extraction = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._files: List[str] = []
        self._current_file: Optional[str] = None
        self._redactions: Dict[str, List[RedactionBox]] = {}  # filepath -> boxes
        self._page_widgets: List[PageWidget] = []
        self._dpi = _DEFAULT_DPI
        self._draw_mode = False
        self._erase_mode = False
        self._output_folder: Optional[str] = None
        self._saved_files: List[str] = []
        self._worker = None
        self._save_worker = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # spaCy warning if missing
        if not _HAS_SPACY:
            warn = QLabel("spaCy not available — using regex-only PII detection. "
                          "Install: pip install spacy && python -m spacy download en_core_web_sm")
            warn.setWordWrap(True)
            warn.setStyleSheet("padding: 6px; border: 1px solid #f38ba8; border-radius: 4px;")
            root.addWidget(warn)

        # Top section: drop zone + file list
        top_splitter = QSplitter(Qt.Horizontal)

        # Drop zone (left)
        self._drop_zone = DropZone()
        self._drop_zone.files_dropped.connect(self._add_files)
        self._drop_zone.clicked.connect(self._browse_files)
        top_splitter.addWidget(self._drop_zone)

        # File list (right)
        file_panel = QWidget()
        fp_layout = QVBoxLayout(file_panel)
        fp_layout.setContentsMargins(0, 0, 0, 0)
        fp_header = QHBoxLayout()
        fp_header.addWidget(QLabel("Files"))
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear_files)
        fp_header.addWidget(clear_btn)
        fp_layout.addLayout(fp_header)
        self._file_list = QListWidget()
        self._file_list.currentRowChanged.connect(self._on_file_selected)
        fp_layout.addWidget(self._file_list)
        top_splitter.addWidget(file_panel)
        top_splitter.setSizes([350, 250])
        root.addWidget(top_splitter)

        # Toolbar
        toolbar = QHBoxLayout()
        self._auto_btn = QPushButton("Auto Redact")
        self._auto_btn.setObjectName("primaryButton")
        self._auto_btn.clicked.connect(self._auto_redact)
        toolbar.addWidget(self._auto_btn)

        self._draw_btn = QToolButton()
        self._draw_btn.setText("Draw Box")
        self._draw_btn.setCheckable(True)
        self._draw_btn.toggled.connect(self._toggle_draw)
        toolbar.addWidget(self._draw_btn)

        self._erase_btn = QToolButton()
        self._erase_btn.setText("Erase Box")
        self._erase_btn.setCheckable(True)
        self._erase_btn.toggled.connect(self._toggle_erase)
        toolbar.addWidget(self._erase_btn)

        zoom_in = QPushButton("+Zoom")
        zoom_in.clicked.connect(lambda: self._zoom(30))
        toolbar.addWidget(zoom_in)
        zoom_out = QPushButton("-Zoom")
        zoom_out.clicked.connect(lambda: self._zoom(-30))
        toolbar.addWidget(zoom_out)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        toolbar.addWidget(self._progress, 1)
        toolbar.addStretch()
        root.addLayout(toolbar)

        # Redaction summary (shown after auto-redact)
        self._summary_label = QLabel("")
        self._summary_label.setWordWrap(True)
        self._summary_label.setVisible(False)
        root.addWidget(self._summary_label)

        # Main area: PDF viewer + redactions panel
        main_splitter = QSplitter(Qt.Horizontal)

        # PDF viewer (scrollable)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._page_container = QWidget()
        self._page_layout = QVBoxLayout(self._page_container)
        self._page_layout.setSpacing(4)
        self._page_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self._scroll.setWidget(self._page_container)
        main_splitter.addWidget(self._scroll)

        # Redactions panel (right)
        redact_panel = QWidget()
        rp_layout = QVBoxLayout(redact_panel)
        rp_layout.setContentsMargins(4, 4, 4, 4)
        rp_layout.addWidget(QLabel("Redactions"))
        self._redact_list = QListWidget()
        self._redact_list.itemClicked.connect(self._on_redact_item_clicked)
        rp_layout.addWidget(self._redact_list)
        self._no_redact_label = QLabel("No redactions yet.\nClick Auto Redact.")
        self._no_redact_label.setObjectName("subtitleLabel")
        self._no_redact_label.setAlignment(Qt.AlignCenter)
        rp_layout.addWidget(self._no_redact_label)
        main_splitter.addWidget(redact_panel)
        main_splitter.setSizes([500, 200])
        root.addWidget(main_splitter, 1)

        # Bottom action bar
        bottom = QHBoxLayout()
        self._save_selected_btn = QPushButton("Redact && Save Selected")
        self._save_selected_btn.clicked.connect(lambda: self._save_redacted(selected_only=True))
        bottom.addWidget(self._save_selected_btn)

        self._save_all_btn = QPushButton("Redact && Save All")
        self._save_all_btn.setObjectName("primaryButton")
        self._save_all_btn.clicked.connect(lambda: self._save_redacted(selected_only=False))
        bottom.addWidget(self._save_all_btn)

        self._status_label = QLabel("")
        bottom.addWidget(self._status_label, 1)

        self._send_btn = QPushButton("Send to Claude Extraction Pack \u2192")
        self._send_btn.setEnabled(False)
        self._send_btn.clicked.connect(self._send_to_extraction)
        bottom.addWidget(self._send_btn)
        root.addLayout(bottom)

    # ── File management ──

    def load_files(self, paths: list):
        """Public method to load files from another tab."""
        self._add_files(paths)

    def _add_files(self, paths: list):
        for p in paths:
            if p not in self._files:
                self._files.append(p)
                item = QListWidgetItem(os.path.basename(p))
                item.setData(Qt.UserRole, p)
                item.setToolTip(p)
                self._file_list.addItem(item)
                if p not in self._redactions:
                    self._redactions[p] = []
        self._drop_zone.set_count(len(self._files))
        self._send_btn.setEnabled(bool(self._files))
        if self._files and not self._current_file:
            self._file_list.setCurrentRow(0)

    def _clear_files(self):
        self._files.clear()
        self._redactions.clear()
        self._file_list.clear()
        self._current_file = None
        self._clear_viewer()
        self._drop_zone.set_count(0)

    def _browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select PDFs", "", "PDF Files (*.pdf)"
        )
        if files:
            self._add_files(files)

    def _on_file_selected(self, row: int):
        if row < 0:
            return
        item = self._file_list.item(row)
        if not item:
            return
        path = item.data(Qt.UserRole)
        if path != self._current_file:
            self._current_file = path
            self._render_file(path)
            self._update_redactions_panel()

    # ── PDF rendering ──

    def _clear_viewer(self):
        for pw in self._page_widgets:
            pw.deleteLater()
        self._page_widgets.clear()

    def _render_file(self, filepath: str):
        self._clear_viewer()
        try:
            doc = fitz.open(filepath)
            scale = self._dpi / 72.0
            mat = fitz.Matrix(scale, scale)
            for page_num in range(len(doc)):
                page = doc[page_num]
                pix = page.get_pixmap(matrix=mat)
                img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(img)

                pw = PageWidget(page_num)
                pw.set_pixmap(pixmap, scale)
                pw.set_boxes(self._redactions.get(filepath, []))
                pw.box_drawn.connect(self._on_box_drawn)
                pw.box_clicked.connect(self._on_box_clicked)
                if self._draw_mode:
                    pw.set_drawing_mode(True)
                if self._erase_mode:
                    pw.set_erasing_mode(True)
                self._page_layout.addWidget(pw)
                self._page_widgets.append(pw)
            doc.close()
        except Exception as e:
            logger.debug("Render error: %s", e)
            lbl = QLabel(f"Error rendering: {e}")
            self._page_layout.addWidget(lbl)

    # ── Toolbar actions ──

    def _auto_redact(self):
        if not self._current_file:
            QMessageBox.information(self, "No File", "Select a PDF file first.")
            return
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._auto_btn.setEnabled(False)
        self._worker = AutoRedactWorker(self._current_file)
        self._worker.progress.connect(lambda c, t: (
            self._progress.setMaximum(t), self._progress.setValue(c)
        ))
        self._worker.page_done.connect(self._on_auto_page_done)
        self._worker.finished.connect(self._on_auto_finished)
        self._worker.start()

    def _on_auto_page_done(self, page_num: int, boxes: list):
        if self._current_file:
            existing = self._redactions.setdefault(self._current_file, [])
            existing.extend(boxes)

    def _on_auto_finished(self, counts: dict):
        self._progress.setVisible(False)
        self._auto_btn.setEnabled(True)
        self._worker = None

        # Show summary
        total = counts.get("total", 0)
        if total > 0:
            parts = []
            if counts.get("names"):
                parts.append(f"{counts['names']} names")
            if counts.get("addresses"):
                parts.append(f"{counts['addresses']} addresses")
            if counts.get("phones"):
                parts.append(f"{counts['phones']} phone numbers")
            if counts.get("refs"):
                parts.append(f"{counts['refs']} reference numbers")
            self._summary_label.setText(f"Found {total} items to redact: {', '.join(parts)}")
            self._summary_label.setStyleSheet("padding: 6px; border: 1px solid #a6e3a1; border-radius: 4px;")
        else:
            self._summary_label.setText("No PII detected automatically. Use Draw Box to manually mark sensitive areas.")
            self._summary_label.setStyleSheet("padding: 6px; border: 1px solid #f9e2af; border-radius: 4px;")
        self._summary_label.setVisible(True)
        # Re-render to show boxes
        if self._current_file:
            self._render_file(self._current_file)
            self._update_redactions_panel()
        # Groq second pass
        try:
            from src.services.ai_redactor import groq_redactor
            from src.services.ai_classifier import groq_classifier
            if groq_classifier.is_available() and self._current_file:
                doc = fitz.open(self._current_file)
                lines = []
                for page in doc:
                    lines.extend(page.get_text().splitlines())
                doc.close()
                missed = groq_redactor.redact_pass(lines)
                if missed:
                    doc2 = fitz.open(self._current_file)
                    for pii_text in missed:
                        for page_num in range(len(doc2)):
                            rects = doc2[page_num].search_for(pii_text)
                            for r in rects:
                                self._redactions.setdefault(self._current_file, []).append(
                                    RedactionBox(page_num, (r.x0, r.y0, r.x1, r.y1), "AUTO", pii_text)
                                )
                    doc2.close()
                    self._render_file(self._current_file)
                    self._update_redactions_panel()
        except Exception:
            pass

    def _toggle_draw(self, checked: bool):
        self._draw_mode = checked
        if checked:
            self._erase_btn.setChecked(False)
        for pw in self._page_widgets:
            pw.set_drawing_mode(checked)

    def _toggle_erase(self, checked: bool):
        self._erase_mode = checked
        if checked:
            self._draw_btn.setChecked(False)
        for pw in self._page_widgets:
            pw.set_erasing_mode(checked)

    def _zoom(self, delta: int):
        self._dpi = max(_MIN_DPI, min(_MAX_DPI, self._dpi + delta))
        if self._current_file:
            self._render_file(self._current_file)

    def _on_box_drawn(self, page_num: int, pdf_rect: tuple):
        if self._current_file:
            box = RedactionBox(page_num, pdf_rect, "MANUAL", "")
            self._redactions.setdefault(self._current_file, []).append(box)
            self._render_file(self._current_file)
            self._update_redactions_panel()

    def _on_box_clicked(self, page_num: int, point: QPoint):
        # Erase mode: find and remove the box containing this point
        if not self._current_file:
            return
        px, py = point.x() / 100.0, point.y() / 100.0
        boxes = self._redactions.get(self._current_file, [])
        for i, box in enumerate(boxes):
            if box.page_num != page_num:
                continue
            x0, y0, x1, y1 = box.pdf_rect
            if x0 <= px <= x1 and y0 <= py <= y1:
                boxes.pop(i)
                self._render_file(self._current_file)
                self._update_redactions_panel()
                return

    # ── Redactions panel ──

    def _update_redactions_panel(self):
        self._redact_list.clear()
        if not self._current_file:
            self._no_redact_label.setVisible(True)
            return
        boxes = self._redactions.get(self._current_file, [])
        self._no_redact_label.setVisible(len(boxes) == 0)
        for i, box in enumerate(boxes):
            label = f"Page {box.page_num + 1}  [{box.type}]"
            if box.text:
                label += f'  "{box.text[:30]}"'
            else:
                label += "  Manual box"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, i)
            self._redact_list.addItem(item)

    def _on_redact_item_clicked(self, item: QListWidgetItem):
        idx = item.data(Qt.UserRole)
        if self._current_file and idx is not None:
            boxes = self._redactions.get(self._current_file, [])
            if 0 <= idx < len(boxes):
                # Scroll to that page
                page_num = boxes[idx].page_num
                if page_num < len(self._page_widgets):
                    self._scroll.ensureWidgetVisible(self._page_widgets[page_num])

    # ── Save ──

    def _save_redacted(self, selected_only: bool):
        if selected_only:
            items = [(self._current_file, self._redactions.get(self._current_file, []))]
            if not self._current_file:
                return
        else:
            items = [(f, self._redactions.get(f, [])) for f in self._files]

        if not self._output_folder:
            folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
            if not folder:
                return
            self._output_folder = folder

        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._save_all_btn.setEnabled(False)
        self._save_selected_btn.setEnabled(False)
        self._save_worker = SaveWorker(items, self._output_folder)
        self._save_worker.progress.connect(
            lambda c, t: (self._progress.setMaximum(t), self._progress.setValue(c))
        )
        self._save_worker.finished.connect(self._on_save_finished)
        self._save_worker.start()

    def _on_save_finished(self, count: int, folder: str):
        self._progress.setVisible(False)
        self._save_all_btn.setEnabled(True)
        self._save_selected_btn.setEnabled(True)
        self._save_worker = None
        self._status_label.setText(f"Saved {count} file(s) to {folder}")
        # Collect saved file paths
        self._saved_files = []
        for f in self._files:
            stem = os.path.splitext(os.path.basename(f))[0]
            redacted = os.path.join(folder, f"{stem}_REDACTED.pdf")
            if os.path.exists(redacted):
                self._saved_files.append(redacted)
        # saved_files populated for send-to-extraction to use redacted paths
        # Update file list badges
        for i in range(self._file_list.count()):
            item = self._file_list.item(i)
            path = item.data(Qt.UserRole)
            stem = os.path.splitext(os.path.basename(path))[0]
            if os.path.exists(os.path.join(folder, f"{stem}_REDACTED.pdf")):
                item.setText(f"Saved {os.path.basename(path)}")

    def _send_to_extraction(self):
        # Prefer saved redacted files if available, otherwise send originals
        paths = self._saved_files if self._saved_files else self._files
        if paths:
            self.send_to_extraction.emit(paths)

    # ── Drag and drop on the tab itself ──

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
