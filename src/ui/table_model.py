"""
Qt table model for the document records.
"""
from typing import List, Any, Optional

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QColor

from src.core.models import DocumentRecord, RenameStatus, DuplicateStatus

COLUMNS = [
    "Original Filename",
    "WHO",
    "DATE",
    "ENTITY",
    "WHAT",
    "Proposed Filename",
    "Confidence",
    "Confidence Reason",
    "Duplicate",
    "Status",
]

EDITABLE_COLUMNS = {1, 2, 3, 4}  # WHO, DATE, ENTITY, WHAT


def _rebuild_filename(rec: DocumentRecord):
    """Rebuild proposed filename, keeping DUPLICATE.pdf for duplicate records."""
    if rec.duplicate_status not in (DuplicateStatus.NONE, None):
        rec.proposed_filename = "DUPLICATE.pdf"
    else:
        rec.proposed_filename = rec.build_proposed_filename()


class DocumentTableModel(QAbstractTableModel):
    """Table model backed by a list of DocumentRecords."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._records: List[DocumentRecord] = []

    def set_records(self, records: List[DocumentRecord]):
        self.beginResetModel()
        self._records = records
        self.endResetModel()

    def get_records(self) -> List[DocumentRecord]:
        return self._records

    def get_record(self, row: int) -> Optional[DocumentRecord]:
        if 0 <= row < len(self._records):
            return self._records[row]
        return None

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._records)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        if row >= len(self._records):
            return None

        rec = self._records[row]

        if role == Qt.DisplayRole or role == Qt.EditRole:
            if col == 0:
                return rec.original_filename
            elif col == 1:
                return rec.who
            elif col == 2:
                return rec.date
            elif col == 3:
                return rec.entity
            elif col == 4:
                return rec.what
            elif col == 5:
                return rec.proposed_filename
            elif col == 6:
                return str(rec.confidence)
            elif col == 7:
                return rec.confidence_breakdown.reasons() if rec.confidence_breakdown else ""
            elif col == 8:
                return rec.duplicate_status.value if rec.duplicate_status else ""
            elif col == 9:
                return rec.rename_status.value if rec.rename_status else ""

        elif role == Qt.BackgroundRole:
            if rec.is_unsure:
                return QColor("#4a3000")  # Amber warning
            if rec.duplicate_status != DuplicateStatus.NONE:
                return QColor("#3a1a1a")  # Red-ish warning
            if rec.rename_status == RenameStatus.RENAMED:
                return QColor("#1a3a1a")  # Green success
            if rec.rename_status == RenameStatus.ERROR:
                return QColor("#3a1a1a")
            if col == 6:
                conf = rec.confidence
                if conf >= 80:
                    return QColor("#1a3a1a")
                elif conf >= 60:
                    return QColor("#3a3a1a")
                else:
                    return QColor("#3a1a1a")

        elif role == Qt.ToolTipRole:
            if col == 7:
                return rec.confidence_breakdown.reasons() if rec.confidence_breakdown else ""
            if col == 8 and rec.duplicate_status != DuplicateStatus.NONE:
                return f"Duplicate: {rec.duplicate_status.value}"
            if col == 9 and rec.error_message:
                return rec.error_message

        return None

    def setData(self, index: QModelIndex, value: Any, role=Qt.EditRole) -> bool:
        if not index.isValid() or role != Qt.EditRole:
            return False
        row = index.row()
        col = index.column()
        if row >= len(self._records):
            return False

        rec = self._records[row]
        value = str(value).strip()

        if col == 1:
            rec.who = value
        elif col == 2:
            rec.date = value
        elif col == 3:
            rec.entity = value
        elif col == 4:
            rec.what = value
        else:
            return False

        # Rebuild proposed filename (preserving DUPLICATE suffix)
        _rebuild_filename(rec)
        # Emit change for the whole row
        self.dataChanged.emit(
            self.index(row, 0),
            self.index(row, self.columnCount() - 1)
        )
        return True

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        base = super().flags(index)
        if index.column() in EDITABLE_COLUMNS:
            return base | Qt.ItemIsEditable
        return base

    def update_record(self, row: int, record: DocumentRecord):
        if 0 <= row < len(self._records):
            self._records[row] = record
            self.dataChanged.emit(
                self.index(row, 0),
                self.index(row, self.columnCount() - 1)
            )

    def bulk_set_field(self, rows: List[int], col: int, value: str):
        """Set a field value for multiple rows."""
        for row in rows:
            if 0 <= row < len(self._records):
                rec = self._records[row]
                if col == 1:
                    rec.who = value
                elif col == 2:
                    rec.date = value
                elif col == 3:
                    rec.entity = value
                elif col == 4:
                    rec.what = value
                _rebuild_filename(rec)
        if rows:
            self.dataChanged.emit(
                self.index(min(rows), 0),
                self.index(max(rows), self.columnCount() - 1)
            )

    def find_replace(self, rows: List[int], find: str, replace: str):
        """Find and replace in proposed filenames for selected rows."""
        for row in rows:
            if 0 <= row < len(self._records):
                rec = self._records[row]
                if find.lower() in rec.what.lower():
                    rec.what = rec.what.replace(find, replace)
                    _rebuild_filename(rec)
        if rows:
            self.dataChanged.emit(
                self.index(min(rows), 0),
                self.index(max(rows), self.columnCount() - 1)
            )
