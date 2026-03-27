"""
Background worker thread for PDF processing.
"""
from typing import List

from PySide6.QtCore import QThread, Signal

from src.core.models import DocumentRecord
from src.core.settings import Settings
from src.services.inference_pipeline import process_batch


class ProcessingWorker(QThread):
    """Worker thread that processes PDF files in the background."""
    progress = Signal(int, int)  # current, total
    finished = Signal(list)  # List[DocumentRecord]
    error = Signal(str)

    def __init__(self, file_paths: List[str], settings: Settings, parent=None):
        super().__init__(parent)
        self._file_paths = file_paths
        self._settings = settings

    def run(self):
        try:
            records = process_batch(
                self._file_paths,
                self._settings,
                progress_callback=lambda cur, tot: self.progress.emit(cur, tot)
            )
            self.finished.emit(records)
        except Exception as e:
            self.error.emit(str(e))
