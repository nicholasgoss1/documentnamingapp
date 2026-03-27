"""
Rename history viewer dialog.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHBoxLayout, QLabel, QHeaderView
)
from PySide6.QtCore import Qt

from src.services.rename_service import get_rename_history


class HistoryDialog(QDialog):
    """Dialog showing rename history from rollback manifests."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Rename History")
        self.setMinimumSize(800, 500)
        self._build_ui()
        self._load_history()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("Rename History")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels([
            "Timestamp", "Original Filename", "New Filename", "Status"
        ])
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table, 1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _load_history(self):
        history = get_rename_history()
        rows = []
        for batch in history:
            ts = batch.get("timestamp", "Unknown")
            for op in batch.get("operations", []):
                rows.append((
                    ts,
                    op.get("original_filename", ""),
                    op.get("proposed_filename", ""),
                    "Renamed"
                ))

        self._table.setRowCount(len(rows))
        for i, (ts, orig, new, status) in enumerate(rows):
            self._table.setItem(i, 0, QTableWidgetItem(ts))
            self._table.setItem(i, 1, QTableWidgetItem(orig))
            self._table.setItem(i, 2, QTableWidgetItem(new))
            self._table.setItem(i, 3, QTableWidgetItem(status))
