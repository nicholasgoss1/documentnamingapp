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

# ── Groq PII detection (replaces spaCy) ──

def _groq_available() -> bool:
    try:
        from src.services.ai_classifier import groq_classifier
        return groq_classifier.is_available()
    except Exception:
        return False


def _detect_pii_with_groq(text: str, few_shot_block: str = "") -> list:
    """Use Groq to detect PII strings in text. Returns list of strings."""
    try:
        from src.services.ai_classifier import _GROQ_API_KEY
        if not _GROQ_API_KEY or _GROQ_API_KEY == "gsk_PASTE_YOUR_KEY_HERE":
            return []
        from groq import Groq
        import json as _json
        client = Groq(api_key=_GROQ_API_KEY)

        system_content = (
            "You are a privacy redaction assistant for Australian insurance documents. "
            "Find all personally identifiable information in the text. Return ONLY "
            "a JSON object with key 'pii_items' containing a list of exact strings to "
            "redact. Include: full names (2+ words), complete addresses, phone numbers, "
            "email addresses, policy numbers, claim numbers, job numbers, ABN/ACN numbers. "
            "Do NOT include company names like insurers or builders. Only personal client info."
        )
        if few_shot_block:
            system_content += "\n\n" + few_shot_block

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": f"Find all PII:\n\n{text[:3000]}"},
            ],
            response_format={"type": "json_object"},
            timeout=10,
        )
        result = _json.loads(response.choices[0].message.content)
        items = result.get("pii_items", [])
        return [str(x).strip() for x in items if x and len(str(x).strip()) >= 2]
    except Exception as e:
        logger.error("Groq PII detection failed: %s", e)
        return []

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


def _search_pii_on_page(page, page_num, pii_text, box_type, seen):
    """Search for PII text on a page, return list of non-overlapping RedactionBox."""
    boxes = []
    try:
        for r in page.search_for(pii_text.strip()):
            key = (page_num, round(r.x0, 1), round(r.y0, 1), round(r.x1, 1), round(r.y1, 1))
            if key not in seen:
                seen.add(key)
                boxes.append(RedactionBox(page_num, (r.x0, r.y0, r.x1, r.y1), box_type, pii_text.strip()))
    except Exception:
        pass
    return boxes


class RegexRedactWorker(QThread):
    """Background worker — regex PII detection only (no Groq)."""
    progress = Signal(int, int)
    page_done = Signal(int, list)
    finished = Signal(dict)

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self._file_path = file_path

    def run(self):
        counts = {"names": 0, "addresses": 0, "phones": 0, "refs": 0, "total": 0}
        try:
            doc = fitz.open(self._file_path)
            for page_num in range(len(doc)):
                self.progress.emit(page_num + 1, len(doc))
                page = doc[page_num]
                text = page.get_text()
                boxes = []
                seen = set()

                for m in _RE_LABEL_VALUE.finditer(text):
                    v = m.group(1).strip()
                    if len(v) >= 3:
                        b = _search_pii_on_page(page, page_num, v, "AUTO", seen)
                        counts["names"] += len(b)
                        boxes.extend(b)

                for m in _RE_ADDRESS.finditer(text):
                    b = _search_pii_on_page(page, page_num, m.group(), "AUTO", seen)
                    counts["addresses"] += len(b)
                    boxes.extend(b)

                for m in _RE_STREET.finditer(text):
                    b = _search_pii_on_page(page, page_num, m.group(), "AUTO", seen)
                    counts["addresses"] += len(b)
                    boxes.extend(b)

                for m in _RE_PHONE.finditer(text):
                    mt = m.group().strip()
                    if len(mt) >= 8:
                        b = _search_pii_on_page(page, page_num, mt, "AUTO", seen)
                        counts["phones"] += len(b)
                        boxes.extend(b)

                for m in _RE_POLICY.finditer(text):
                    b = _search_pii_on_page(page, page_num, m.group(), "AUTO", seen)
                    counts["refs"] += len(b)
                    boxes.extend(b)

                for m in _RE_REF_LABEL.finditer(text):
                    ref = m.group(1).strip()
                    if len(ref) >= 4:
                        b = _search_pii_on_page(page, page_num, ref, "AUTO", seen)
                        counts["refs"] += len(b)
                        boxes.extend(b)

                for m in _RE_ACCOUNT.finditer(text):
                    b = _search_pii_on_page(page, page_num, m.group(), "AUTO", seen)
                    counts["refs"] += len(b)
                    boxes.extend(b)

                self.page_done.emit(page_num, boxes)
            doc.close()
        except Exception as e:
            logger.debug("Regex redact error: %s", e)
        counts["total"] = counts["names"] + counts["addresses"] + counts["phones"] + counts["refs"]
        self.finished.emit(counts)


class AIRedactWorker(QThread):
    """Background worker — Groq AI PII detection only. Boxes typed as 'AI'."""
    progress = Signal(str)  # status message
    finished = Signal(list, int)  # list of RedactionBox, count

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self._file_path = file_path

    def run(self):
        all_boxes = []
        try:
            self.progress.emit("Extracting text...")
            doc = fitz.open(self._file_path)
            full_text = "\n".join(page.get_text() for page in doc)

            self.progress.emit("Sending to Groq AI...")
            # Build prompt with corrections few-shot
            from src.services.redaction_corrections import build_redaction_few_shot
            few_shot = build_redaction_few_shot()

            pii_items = _detect_pii_with_groq(full_text, few_shot_block=few_shot)

            if pii_items:
                self.progress.emit(f"Found {len(pii_items)} items, locating on pages...")
                seen = set()
                for pii_text in pii_items:
                    for page_num in range(len(doc)):
                        page = doc[page_num]
                        boxes = _search_pii_on_page(page, page_num, pii_text, "AI", seen)
                        all_boxes.extend(boxes)

            doc.close()
        except Exception as e:
            logger.debug("AI redact error: %s", e)
        self.finished.emit(all_boxes, len(all_boxes))


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
            if box.type == "AI":
                # AI boxes: red border + light red fill so user can distinguish
                painter.fillRect(rect, QColor(255, 0, 0, 60))
                painter.setPen(QPen(QColor(255, 0, 0), 2))
                painter.drawRect(rect)
                painter.setPen(Qt.NoPen)
            elif box.type == "AUTO":
                # Regex boxes: solid red fill
                painter.fillRect(rect, QColor(255, 0, 0, 120))
            else:
                # Manual boxes: black fill
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

        # Groq availability warning
        if not _groq_available():
            warn = QLabel("AI name detection unavailable \u2014 regex only active. "
                          "Use Draw Box to mark names manually.")
            warn.setWordWrap(True)
            warn.setStyleSheet("padding: 6px; border: 1px solid #f9e2af; border-radius: 4px;")
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
        self._files_select_all_btn = QPushButton("\u2611 All")
        self._files_select_all_btn.setFixedHeight(24)
        self._files_select_all_btn.setFixedWidth(50)
        self._files_select_all_btn.clicked.connect(self._toggle_files_select_all)
        fp_header.addWidget(self._files_select_all_btn)
        remove_sel_btn = QPushButton("Remove Sel.")
        remove_sel_btn.setFixedHeight(24)
        remove_sel_btn.clicked.connect(self._remove_selected_files)
        fp_header.addWidget(remove_sel_btn)
        clear_btn = QPushButton("Clear All")
        clear_btn.setFixedHeight(24)
        clear_btn.clicked.connect(self._clear_files)
        fp_header.addWidget(clear_btn)
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
        self._file_list.currentRowChanged.connect(self._on_file_selected)
        fp_layout.addWidget(self._file_list)
        top_splitter.addWidget(file_panel)
        top_splitter.setSizes([350, 250])
        root.addWidget(top_splitter)

        # Toolbar
        toolbar = QHBoxLayout()
        self._regex_btn = QPushButton("Regex Redact")
        self._regex_btn.clicked.connect(self._regex_redact)
        toolbar.addWidget(self._regex_btn)

        self._ai_btn = QPushButton("AI Redact")
        self._ai_btn.setObjectName("primaryButton")
        self._ai_btn.clicked.connect(self._ai_redact)
        if not _groq_available():
            self._ai_btn.setEnabled(False)
            self._ai_btn.setToolTip("Groq AI unavailable")
        toolbar.addWidget(self._ai_btn)

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

        rp_header = QHBoxLayout()
        rp_header.addWidget(QLabel("Redactions"))
        self._select_all_btn = QPushButton("\u2611 Select All")
        self._select_all_btn.setFixedHeight(26)
        self._select_all_btn.setStyleSheet("font-size: 12px; padding: 2px 8px;")
        self._select_all_btn.clicked.connect(self._toggle_select_all)
        rp_header.addWidget(self._select_all_btn)
        rp_layout.addLayout(rp_header)

        self._redact_list = QListWidget()
        self._redact_list.setStyleSheet("""
            QListWidget::indicator {
                width: 16px; height: 16px;
                border: 2px solid #89b4fa;
                border-radius: 3px;
                background: #313244;
            }
            QListWidget::indicator:checked {
                background: #89b4fa;
                border-color: #89b4fa;
            }
        """)
        self._redact_list.itemClicked.connect(self._on_redact_item_clicked)
        rp_layout.addWidget(self._redact_list)

        self._no_redact_label = QLabel("No redactions yet.\nClick Regex Redact or AI Redact.")
        self._no_redact_label.setObjectName("subtitleLabel")
        self._no_redact_label.setAlignment(Qt.AlignCenter)
        rp_layout.addWidget(self._no_redact_label)

        self._remove_selected_btn = QPushButton("Remove Selected")
        self._remove_selected_btn.setObjectName("dangerButton")
        self._remove_selected_btn.clicked.connect(self._remove_selected_boxes)
        rp_layout.addWidget(self._remove_selected_btn)

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
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
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
        self._send_btn.setEnabled(False)

    def _toggle_files_select_all(self):
        count = self._file_list.count()
        if count == 0:
            return
        all_checked = all(
            self._file_list.item(i).checkState() == Qt.Checked for i in range(count)
        )
        new_state = Qt.Unchecked if all_checked else Qt.Checked
        for i in range(count):
            self._file_list.item(i).setCheckState(new_state)
        self._files_select_all_btn.setText("\u2610 All" if not all_checked else "\u2611 All")

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
            self._redactions.pop(path, None)
        # If current file was removed, clear preview
        if self._current_file in to_remove:
            self._current_file = None
            self._clear_viewer()
        # Rebuild file list widget
        self._file_list.clear()
        for p in self._files:
            item = QListWidgetItem(os.path.basename(p))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            item.setData(Qt.UserRole, p)
            item.setToolTip(p)
            self._file_list.addItem(item)
        self._drop_zone.set_count(len(self._files))
        self._send_btn.setEnabled(bool(self._files))
        if self._files and not self._current_file:
            self._file_list.setCurrentRow(0)

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

    def _get_doc_type(self) -> str:
        """Extract document type from filename for corrections logging.
        Strips dollar amounts so 'Quote $55,208.19' becomes 'Quote'.
        """
        if not self._current_file:
            return ""
        fn = os.path.basename(self._current_file)
        name = os.path.splitext(fn)[0]
        segments = [s.strip() for s in name.split(" - ")]
        doc_type = segments[3] if len(segments) >= 4 else segments[-1] if segments else ""
        return re.sub(r'\s*\$[\d,]+\.?\d*', '', doc_type).strip()

    def _regex_redact(self):
        """Run regex-only PII detection (no Groq)."""
        if not self._current_file:
            QMessageBox.information(self, "No File", "Select a PDF file first.")
            return
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._regex_btn.setEnabled(False)
        self._worker = RegexRedactWorker(self._current_file)
        self._worker.progress.connect(lambda c, t: (
            self._progress.setMaximum(t), self._progress.setValue(c)
        ))
        self._worker.page_done.connect(self._on_regex_page_done)
        self._worker.finished.connect(self._on_regex_finished)
        self._worker.start()

    def _on_regex_page_done(self, page_num: int, boxes: list):
        if self._current_file:
            self._redactions.setdefault(self._current_file, []).extend(boxes)

    def _on_regex_finished(self, counts: dict):
        self._progress.setVisible(False)
        self._regex_btn.setEnabled(True)
        self._worker = None
        total = counts.get("total", 0)
        if total > 0:
            parts = []
            if counts.get("names"):
                parts.append(f"{counts['names']} label values")
            if counts.get("addresses"):
                parts.append(f"{counts['addresses']} addresses")
            if counts.get("phones"):
                parts.append(f"{counts['phones']} phones")
            if counts.get("refs"):
                parts.append(f"{counts['refs']} refs")
            self._summary_label.setText(f"Regex found {total} items: {', '.join(parts)}")
            self._summary_label.setStyleSheet("padding: 6px; border: 1px solid #a6e3a1; border-radius: 4px;")
        else:
            self._summary_label.setText("No PII found by regex. Try AI Redact or Draw Box.")
            self._summary_label.setStyleSheet("padding: 6px; border: 1px solid #f9e2af; border-radius: 4px;")
        self._summary_label.setVisible(True)
        if self._current_file:
            self._render_file(self._current_file)
            self._update_redactions_panel()

    def _ai_redact(self):
        """Run Groq AI PII detection (separate from regex)."""
        if not self._current_file:
            QMessageBox.information(self, "No File", "Select a PDF file first.")
            return
        if not _groq_available():
            self._summary_label.setText("AI unavailable. Use Regex Redact or Draw Box.")
            self._summary_label.setStyleSheet("padding: 6px; border: 1px solid #f38ba8; border-radius: 4px;")
            self._summary_label.setVisible(True)
            return
        self._ai_btn.setEnabled(False)
        self._summary_label.setText("Sending to Groq AI...")
        self._summary_label.setStyleSheet("padding: 6px; border: 1px solid #89b4fa; border-radius: 4px;")
        self._summary_label.setVisible(True)
        self._worker = AIRedactWorker(self._current_file)
        self._worker.progress.connect(lambda msg: self._summary_label.setText(msg))
        self._worker.finished.connect(self._on_ai_finished)
        self._worker.start()

    def _on_ai_finished(self, boxes: list, count: int):
        self._ai_btn.setEnabled(True)
        self._worker = None
        if self._current_file and boxes:
            self._redactions.setdefault(self._current_file, []).extend(boxes)
            self._render_file(self._current_file)
            self._update_redactions_panel()
        if count > 0:
            self._summary_label.setText(f"AI found {count} items to redact")
            self._summary_label.setStyleSheet("padding: 6px; border: 1px solid #a6e3a1; border-radius: 4px;")
        else:
            self._summary_label.setText("AI found no additional PII. Use Draw Box if needed.")
            self._summary_label.setStyleSheet("padding: 6px; border: 1px solid #f9e2af; border-radius: 4px;")
        self._summary_label.setVisible(True)

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
            # Try to find what text is under this manually drawn box
            drawn_text = ""
            try:
                doc = fitz.open(self._current_file)
                page = doc[page_num]
                rect = fitz.Rect(*pdf_rect)
                drawn_text = page.get_text("text", clip=rect).strip()
                doc.close()
            except Exception:
                pass

            box = RedactionBox(page_num, pdf_rect, "MANUAL", drawn_text)
            self._redactions.setdefault(self._current_file, []).append(box)

            # Log correction: user drew a box = this text should be redacted
            if drawn_text and len(drawn_text) >= 2:
                try:
                    from src.services.redaction_corrections import log_redaction_correction
                    log_redaction_correction(self._get_doc_type(), drawn_text, "should_redact")
                except Exception:
                    pass

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
                # Log correction if erasing an AI box
                if box.type == "AI" and box.text:
                    try:
                        from src.services.redaction_corrections import log_redaction_correction
                        log_redaction_correction(self._get_doc_type(), box.text, "should_not_redact")
                    except Exception:
                        pass
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
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            item.setData(Qt.UserRole, i)
            self._redact_list.addItem(item)

    def _on_redact_item_clicked(self, item: QListWidgetItem):
        idx = item.data(Qt.UserRole)
        if self._current_file and idx is not None:
            boxes = self._redactions.get(self._current_file, [])
            if 0 <= idx < len(boxes):
                page_num = boxes[idx].page_num
                if page_num < len(self._page_widgets):
                    self._scroll.ensureWidgetVisible(self._page_widgets[page_num])

    def _toggle_select_all(self):
        """Toggle Select All / Deselect All."""
        count = self._redact_list.count()
        if count == 0:
            return
        all_checked = all(
            self._redact_list.item(i).checkState() == Qt.Checked
            for i in range(count)
        )
        new_state = Qt.Unchecked if all_checked else Qt.Checked
        for i in range(count):
            self._redact_list.item(i).setCheckState(new_state)
        if all_checked:
            self._select_all_btn.setText("\u2611 Select All")
        else:
            self._select_all_btn.setText("\u2610 Deselect All")

    def _remove_selected_boxes(self):
        """Remove all checked redaction boxes. Log corrections for AI boxes."""
        if not self._current_file:
            return
        boxes = self._redactions.get(self._current_file, [])
        if not boxes:
            return

        # Collect indices to remove (checked items)
        indices_to_remove = []
        for i in range(self._redact_list.count()):
            item = self._redact_list.item(i)
            if item.checkState() == Qt.Checked:
                idx = item.data(Qt.UserRole)
                if idx is not None:
                    indices_to_remove.append(idx)

        if not indices_to_remove:
            return

        # Log corrections for AI boxes being removed
        doc_type = self._get_doc_type()
        for idx in indices_to_remove:
            if 0 <= idx < len(boxes):
                box = boxes[idx]
                if box.type == "AI" and box.text:
                    try:
                        from src.services.redaction_corrections import log_redaction_correction
                        log_redaction_correction(doc_type, box.text, "should_not_redact")
                    except Exception:
                        pass

        # Remove in reverse order to preserve indices
        for idx in sorted(indices_to_remove, reverse=True):
            if 0 <= idx < len(boxes):
                boxes.pop(idx)

        # Refresh
        self._select_all_btn.setText("Select All")
        self._render_file(self._current_file)
        self._update_redactions_panel()

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
