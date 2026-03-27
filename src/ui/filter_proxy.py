"""
Filter proxy model for the document table.
Supports filtering by confidence, UNSURE, NO DATE, duplicates, etc.
"""
from PySide6.QtCore import QSortFilterProxyModel, QModelIndex, Qt

from src.core.models import DuplicateStatus


class DocumentFilterProxy(QSortFilterProxyModel):
    """Proxy model that supports multiple filter criteria."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_text = ""
        self._filter_low_confidence = False
        self._filter_unsure = False
        self._filter_no_date = False
        self._filter_partial_date = False
        self._filter_missing_who = False
        self._filter_missing_entity = False
        self._filter_missing_what = False
        self._filter_duplicates = False
        self._filter_annexure = False

    def set_search_text(self, text: str):
        self._search_text = text.lower()
        self.invalidateFilter()

    def set_filter(self, name: str, enabled: bool):
        attr = f"_filter_{name}"
        if hasattr(self, attr):
            setattr(self, attr, enabled)
            self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        rec = model.get_record(source_row)
        if rec is None:
            return False

        # Search text filter
        if self._search_text:
            searchable = (
                rec.original_filename.lower()
                + " " + rec.proposed_filename.lower()
                + " " + rec.extracted_text[:500].lower()
                + " " + rec.who.lower()
                + " " + rec.entity.lower()
                + " " + rec.what.lower()
            )
            if self._search_text not in searchable:
                return False

        # Specific filters (any active filter must match)
        if self._filter_low_confidence and rec.confidence >= 60:
            return False
        if self._filter_unsure and not rec.is_unsure:
            return False
        if self._filter_no_date and rec.date != "NO DATE":
            return False
        if self._filter_partial_date:
            if not rec.date or rec.date == "NO DATE" or len(rec.date) == 10:
                return False
        if self._filter_missing_who and rec.who:
            return False
        if self._filter_missing_entity and rec.entity:
            return False
        if self._filter_missing_what and rec.what:
            return False
        if self._filter_duplicates and rec.duplicate_status == DuplicateStatus.NONE:
            return False
        if self._filter_annexure and not rec.annexure_stripped:
            return False

        return True
