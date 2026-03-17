"""
PDF preview widget using PyMuPDF rendering.
"""
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSpinBox
)

from src.services.pdf_extractor import render_page_pixmap, get_page_count


class PdfPreviewWidget(QWidget):
    """Widget that displays a rendered PDF page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._file_path = ""
        self._current_page = 0
        self._page_count = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Title
        self._title = QLabel("PDF Preview")
        self._title.setObjectName("subtitleLabel")
        self._title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._title)

        # Scroll area for the image
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setMinimumSize(QSize(200, 300))
        self._scroll.setWidget(self._image_label)
        layout.addWidget(self._scroll, 1)

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
        """Load a PDF for preview."""
        self._file_path = file_path
        self._page_count = get_page_count(file_path)
        self._current_page = 0
        self._page_spin.setMaximum(max(1, self._page_count))
        self._page_spin.setValue(1)
        self._page_label.setText(f"/ {self._page_count}")
        self._title.setText(file_path.split("/")[-1].split("\\")[-1])
        self._render_current()

    def clear(self):
        self._file_path = ""
        self._page_count = 0
        self._current_page = 0
        self._image_label.clear()
        self._title.setText("PDF Preview")
        self._page_label.setText("/ 0")

    def _render_current(self):
        if not self._file_path:
            return
        png_data = render_page_pixmap(self._file_path, self._current_page, zoom=1.5)
        if png_data:
            img = QImage.fromData(png_data)
            pixmap = QPixmap.fromImage(img)
            # Scale to fit width
            max_w = self._scroll.viewport().width() - 20
            if pixmap.width() > max_w:
                pixmap = pixmap.scaledToWidth(max_w, Qt.SmoothTransformation)
            self._image_label.setPixmap(pixmap)
        else:
            self._image_label.setText("Unable to render page")

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
