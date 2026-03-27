"""
Document preview widget — renders PDF pages via PyMuPDF and shows
plain-text / DOCX content as scrollable text.
"""
import logging
import os

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QImage

logger = logging.getLogger(__name__)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSpinBox, QTextEdit, QStackedWidget,
)

from src.services.pdf_extractor import render_page_pixmap, get_page_count

# Lightweight text readers (duplicated from pdf_extractor to avoid circular
# import if preview_widget is imported before extractor is fully loaded)
_TEXT_EXTS = (".txt",)
_DOCX_EXTS = (".docx",)


def _read_preview_text(path: str) -> str:
    """Return a text preview string for non-PDF files."""
    ext = os.path.splitext(path)[1].lower()
    if ext in _TEXT_EXTS:
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                with open(path, "r", encoding=enc) as f:
                    return f.read(50_000)  # cap at 50 KB for preview
            except (UnicodeDecodeError, LookupError):
                continue
        return "(unable to decode text file)"
    if ext in _DOCX_EXTS:
        try:
            from docx import Document as DocxDocument
            doc = DocxDocument(path)
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as e:
            return f"(unable to read .docx: {e})"
    return ""


class PdfPreviewWidget(QWidget):
    """Widget that displays a rendered PDF page or text preview."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._file_path = ""
        self._current_page = 0
        self._page_count = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Title
        self._title = QLabel("Document Preview")
        self._title.setObjectName("subtitleLabel")
        self._title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._title)

        # Stacked widget: page 0 = image (PDF), page 1 = text (TXT/DOCX)
        self._stack = QStackedWidget()

        # --- Image preview (PDF) ---
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setMinimumSize(QSize(200, 300))
        self._scroll.setWidget(self._image_label)
        self._stack.addWidget(self._scroll)       # index 0

        # --- Text preview (TXT/DOCX) ---
        self._text_view = QTextEdit()
        self._text_view.setReadOnly(True)
        self._stack.addWidget(self._text_view)     # index 1

        layout.addWidget(self._stack, 1)

        # Navigation
        nav = QHBoxLayout()
        self._prev_btn = QPushButton("< Prev")
        self._prev_btn.clicked.connect(self._prev_page)
        nav.addWidget(self._prev_btn)

        self._page_spin = QSpinBox()
        self._page_spin.setMinimum(1)
        self._page_spin.setMaximum(1)
        self._page_spin.setButtonSymbols(QSpinBox.NoButtons)
        self._page_spin.setFixedWidth(50)
        self._page_spin.setAlignment(Qt.AlignCenter)
        self._page_spin.valueChanged.connect(self._go_to_page)
        nav.addWidget(self._page_spin)

        # Explicit up/down buttons (larger click targets than spinbox arrows)
        self._up_btn = QPushButton("\u25B2")
        self._up_btn.setFixedSize(28, 28)
        self._up_btn.setToolTip("Previous page")
        self._up_btn.clicked.connect(self._prev_page)
        nav.addWidget(self._up_btn)

        self._down_btn = QPushButton("\u25BC")
        self._down_btn.setFixedSize(28, 28)
        self._down_btn.setToolTip("Next page")
        self._down_btn.clicked.connect(self._next_page)
        nav.addWidget(self._down_btn)

        self._page_label = QLabel("/ 0")
        nav.addWidget(self._page_label)

        self._next_btn = QPushButton("Next >")
        self._next_btn.clicked.connect(self._next_page)
        nav.addWidget(self._next_btn)

        layout.addLayout(nav)

    def load_pdf(self, file_path: str):
        """Load a document for preview (PDF, TXT, or DOCX)."""
        self._file_path = file_path
        self._page_count = get_page_count(file_path)
        self._current_page = 0
        self._title.setText(file_path.split("/")[-1].split("\\")[-1])

        ext = os.path.splitext(file_path)[1].lower()
        if ext in (".txt", ".docx"):
            # Show text preview
            self._stack.setCurrentIndex(1)
            self._text_view.setPlainText(_read_preview_text(file_path))
            self._page_spin.setMaximum(1)
            self._page_spin.setValue(1)
            self._page_label.setText("/ 1")
            # Hide nav for single-page text docs
            self._prev_btn.setEnabled(False)
            self._next_btn.setEnabled(False)
        else:
            # PDF rendering
            self._stack.setCurrentIndex(0)
            self._page_spin.setMaximum(max(1, self._page_count))
            self._page_spin.setValue(1)
            self._page_label.setText(f"/ {self._page_count}")
            self._prev_btn.setEnabled(True)
            self._next_btn.setEnabled(True)
            self._render_current()

    def clear(self):
        self._file_path = ""
        self._page_count = 0
        self._current_page = 0
        self._image_label.clear()
        self._text_view.clear()
        self._stack.setCurrentIndex(0)
        self._title.setText("Document Preview")
        self._page_label.setText("/ 0")

    def _render_current(self):
        if not self._file_path:
            return
        try:
            # Check for encrypted PDFs
            import fitz
            try:
                doc = fitz.open(self._file_path)
                if doc.is_encrypted:
                    doc.close()
                    self._image_label.setText("This PDF is password protected \u2014 preview unavailable")
                    return
                doc.close()
            except Exception:
                pass

            # Try normal render
            png_data = render_page_pixmap(self._file_path, self._current_page, zoom=1.5)

            # Retry at lower DPI if first attempt fails
            if not png_data:
                logger.debug("Preview render failed at 1.5x for page %d, retrying at 96 DPI", self._current_page)
                png_data = render_page_pixmap(self._file_path, self._current_page, zoom=96/72)

            # Try page 0 as last resort
            if not png_data and self._current_page != 0:
                logger.debug("Retrying with page 0")
                png_data = render_page_pixmap(self._file_path, 0, zoom=96/72)

            if png_data:
                img = QImage.fromData(png_data)
                pixmap = QPixmap.fromImage(img)
                max_w = self._scroll.viewport().width() - 20
                if pixmap.width() > max_w:
                    pixmap = pixmap.scaledToWidth(max_w, Qt.SmoothTransformation)
                self._image_label.setPixmap(pixmap)
            else:
                self._image_label.setText("Preview unavailable for this file")
        except Exception as e:
            logger.debug("Preview render error: %s", e)
            self._image_label.setText("Preview unavailable for this file")

    def _prev_page(self):
        if self._current_page > 0:
            self._current_page -= 1
            self._page_spin.setValue(self._current_page + 1)

    def _next_page(self):
        if self._current_page < self._page_count - 1:
            self._current_page += 1
            self._page_spin.setValue(self._current_page + 1)

    def _go_to_page(self, page_num: int):
        self._current_page = page_num - 1
        self._render_current()
