"""
Qt table model for the document records.
Logs corrections to corrections_store when users edit fields.
"""
import logging
from typing import List, Any, Optional

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal
from PySide6.QtGui import QColor

from src.core.models import DocumentRecord, RenameStatus, DuplicateStatus

logger = logging.getLogger(__name__)

_COL_TO_FIELD = {1: "who", 2: "date", 3: "entity", 4: "what", 8: "duplicate"}

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

EDITABLE_COLUMNS = {1, 2, 3, 4, 8}  # WHO, DATE, ENTITY, WHAT, Duplicate


def _rebuild_filename(rec: DocumentRecord):
    """Rebuild proposed filename, keeping DUPLICATE filename for duplicate records."""
    if rec.duplicate_status not in (DuplicateStatus.NONE, None):
        # Preserve existing DUPLICATE filename (including any collision suffix)
        if not rec.proposed_filename or not rec.proposed_filename.upper().startswith("DUPLICATE"):
            rec.proposed_filename = "DUPLICATE.pdf"
        # else: keep existing "DUPLICATE.pdf", "DUPLICATE (2).pdf", etc.
    else:
        rec.proposed_filename = rec.build_proposed_filename()


class DocumentTableModel(QAbstractTableModel):
    """Table model backed by a list of DocumentRecords."""

    correction_logged = Signal()  # emitted after a correction is saved

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
                if rec.rename_status == RenameStatus.ERROR and rec.error_message:
                    return f"Error: {rec.error_message}"
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

        # Capture before values for correction logging
        field_name = _COL_TO_FIELD.get(col, "")
        old_value = ""
        if col == 1:
            old_value = rec.who
        elif col == 2:
            old_value = rec.date
        elif col == 3:
            old_value = rec.entity
        elif col == 4:
            old_value = rec.what
        elif col == 8:
            old_value = rec.duplicate_status.value if rec.duplicate_status else "None"

        if col == 1:
            rec.who = value
        elif col == 2:
            rec.date = value
        elif col == 3:
            rec.entity = value
        elif col == 4:
            rec.what = value
        elif col == 8:
            _DUP_MAP = {
                "none": DuplicateStatus.NONE,
                "exact duplicate": DuplicateStatus.EXACT_DUPLICATE,
                "near duplicate": DuplicateStatus.LIKELY_DUPLICATE,
                "likely duplicate": DuplicateStatus.LIKELY_DUPLICATE,
            }
            rec.duplicate_status = _DUP_MAP.get(value.lower(), DuplicateStatus.NONE)
        else:
            return False

        # Log correction if value actually changed
        if field_name and value != old_value:
            try:
                from src.services.corrections_store import log_correction
                dup_val = rec.duplicate_status.value if rec.duplicate_status else "None"
                log_correction(
                    original_filename=rec.original_filename,
                    text_snippet=rec.extracted_text[:200] if rec.extracted_text else "",
                    ai_result={
                        "who": rec.who if col != 1 else old_value,
                        "entity": rec.entity if col != 3 else old_value,
                        "date": rec.date if col != 2 else old_value,
                        "what": rec.what if col != 4 else old_value,
                        "duplicate": old_value if col == 8 else dup_val,
                    },
                    corrected_result={
                        "who": rec.who, "entity": rec.entity,
                        "date": rec.date, "what": rec.what,
                        "duplicate": dup_val,
                    },
                    fields_corrected=[field_name],
                )
                self.correction_logged.emit()
            except Exception as e:
                logger.debug("Failed to log correction: %s", e)

        # Manual edit overrides duplicate detection (except when editing duplicate itself)
        if col != 8:
            rec.duplicate_status = DuplicateStatus.NONE
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
                rec.duplicate_status = DuplicateStatus.NONE
                _rebuild_filename(rec)
        if rows:
            self.dataChanged.emit(
                self.index(min(rows), 0),
                self.index(max(rows), self.columnCount() - 1)
            )

    def remove_records(self, rows: List[int]):
        """Remove records at the given row indices."""
        if not rows:
            return
        self.beginResetModel()
        # Remove in reverse order to preserve indices
        for row in sorted(rows, reverse=True):
            if 0 <= row < len(self._records):
                del self._records[row]
        self.endResetModel()

    def find_replace(self, rows: List[int], find: str, replace: str):
        """Find and replace in proposed filenames for selected rows."""
        for row in rows:
            if 0 <= row < len(self._records):
                rec = self._records[row]
                if find.lower() in rec.what.lower():
                    rec.what = rec.what.replace(find, replace)
                    rec.duplicate_status = DuplicateStatus.NONE
                    _rebuild_filename(rec)
        if rows:
            self.dataChanged.emit(
                self.index(min(rows), 0),
                self.index(max(rows), self.columnCount() - 1)
            )
