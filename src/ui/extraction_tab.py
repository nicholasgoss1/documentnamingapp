"""
Claude Extraction Pack tab — Groq-assisted verbatim extraction for AFCA drafting.
"""
import os
import datetime
from collections import defaultdict
from typing import Dict, List

import fitz  # PyMuPDF

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QProgressBar, QTextEdit, QFileDialog, QGroupBox,
    QMessageBox, QApplication,
)

from src.services.smart_extractor import smart_extractor, VP_SECTIONS


# ---------------------------------------------------------------------------
# Worker thread
# ---------------------------------------------------------------------------
class ExtractionWorker(QThread):
    """Background worker that processes PDFs through SmartExtractor."""

    progress = Signal(int, int)       # current, total
    status_msg = Signal(str)          # per-file status
    finished = Signal(str, dict)      # (pack_text, summary_dict)
    error = Signal(str)

    def __init__(self, folder: str, matter_ref: str, date_of_loss: str, parent=None):
        super().__init__(parent)
        self._folder = folder
        self._matter_ref = matter_ref
        self._date_of_loss = date_of_loss

    def run(self):
        try:
            pdf_files = sorted(
                f for f in os.listdir(self._folder)
                if f.lower().endswith(".pdf")
            )
            if not pdf_files:
                self.error.emit("No PDF files found in the selected folder.")
                return

            total = len(pdf_files)
            # Collect results by VP section
            vp_results: Dict[str, list] = defaultdict(list)
            ai_count = 0
            fallback_files: list = []

            for idx, filename in enumerate(pdf_files):
                self.progress.emit(idx + 1, total)
                self.status_msg.emit(f"Processing {filename} \u2014 extracting text...")
                path = os.path.join(self._folder, filename)

                try:
                    doc = fitz.open(path)
                    text_parts = []
                    for page in doc:
                        text_parts.append(page.get_text("text"))
                    full_text = "\n".join(text_parts)
                    doc.close()
                except Exception as e:
                    vp_results["VP_OTHER"].append({
                        "filename": filename,
                        "doc_type": "Unknown",
                        "who": "Unknown",
                        "passages": [{"section": f"[ERROR: {e}]", "page": "UNKNOWN", "text": ""}],
                        "fallback": True,
                        "used_groq": False,
                    })
                    fallback_files.append(filename)
                    continue

                self.status_msg.emit(f"Processing {filename} \u2014 classifying...")
                result = smart_extractor.process_document(full_text, filename)

                vp = result.get("vp_section", "VP_OTHER")
                vp_results[vp].append(result)

                if result.get("used_groq"):
                    ai_count += 1
                if result.get("fallback"):
                    fallback_files.append(filename)

                self.status_msg.emit(
                    f"Processed {filename} \u2014 {result.get('doc_type', 'Unknown')} \u2192 {vp}"
                )

            # Build the verbatim pack text
            pack_text = self._build_pack(vp_results, ai_count, total, fallback_files)

            summary = {
                "total": total,
                "ai_count": ai_count,
                "fallback_count": len(fallback_files),
                "fallback_files": fallback_files,
                "vp_populated": {
                    vp: bool(vp_results.get(vp))
                    for vp in ["VP1", "VP2", "VP3", "VP4", "VP5", "VP6"]
                },
            }

            self.finished.emit(pack_text, summary)
        except Exception as e:
            self.error.emit(str(e))

    def _build_pack(self, vp_results, ai_count, total, fallback_files) -> str:
        today = datetime.date.today().strftime("%d %B %Y")
        lines = []

        # Header
        lines.append("=" * 64)
        lines.append("CLAIMSCO PTY LTD \u2014 VERBATIM PACK")
        lines.append(f"Matter: {self._matter_ref or '(not specified)'}")
        lines.append(f"Date of loss: {self._date_of_loss or '(not specified)'}")
        lines.append(f"Generated: {today}")
        lines.append(f"AI-assisted: {ai_count} of {total} documents used Groq extraction")
        lines.append("PURPOSE: Raw verbatim text for AFCA submission drafting.")
        lines.append("Upload this file to Claude AFCA Assistant v24 alongside the")
        lines.append("Master Evidence File.")
        lines.append("=" * 64)
        lines.append("")

        # VP sections
        vp_order = ["VP1", "VP2", "VP3", "VP4", "VP5", "VP6", "VP_OTHER"]
        vp_labels = {
            "VP1": ("VP1 \u2014 PDS QUOTABLE SECTIONS", "PDS"),
            "VP2": ("VP2 \u2014 COMPLAINANT EXPERT REPORTS", "COMPLAINANT EXPERT"),
            "VP3": ("VP3 \u2014 FF EXPERT REPORTS AND DECISIONS", "FF DECISION"),
            "VP4": ("VP4 \u2014 SCOPES AND QUOTES", "SCOPE"),
            "VP5": ("VP5 \u2014 WEATHER EVIDENCE", "WEATHER"),
            "VP6": ("VP6 \u2014 SOLAR AND SPECIALIST REPORTS", "SPECIALIST"),
            "VP_OTHER": ("OTHER DOCUMENTS", "OTHER"),
        }

        for vp in vp_order:
            results = vp_results.get(vp, [])
            if not results:
                continue

            section_title, default_label = vp_labels.get(vp, (vp, vp))
            lines.append("")
            lines.append("=" * 64)
            lines.append(f"## {section_title}")
            lines.append("=" * 64)
            lines.append("")

            for result in results:
                filename = result.get("filename", "")
                doc_type = result.get("doc_type", "")
                who = result.get("who", "")
                label = f"{who} {default_label}" if who and who != "Unknown" else default_label

                for passage in result.get("passages", []):
                    section = passage.get("section", "")
                    page = passage.get("page", "UNKNOWN")
                    text = passage.get("text", "")

                    lines.append(f"--- {label} | {filename} | Page {page} ---")
                    if section:
                        lines.append(f"SECTION: {section}")
                    if text:
                        lines.append(text)
                    lines.append("")

        # Gaps section
        if fallback_files:
            lines.append("")
            lines.append("=" * 64)
            lines.append("## GAPS \u2014 MANUAL REVIEW REQUIRED")
            lines.append("=" * 64)
            lines.append("")
            lines.append("The following documents used raw text extraction (Groq extraction")
            lines.append("failed or was unavailable). Verify these manually:")
            for fn in fallback_files:
                lines.append(f"  - {fn}")
            lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Extraction Tab widget
# ---------------------------------------------------------------------------
class ExtractionTab(QWidget):
    """Tab 3 - Claude Extraction Pack with Groq-assisted smart extraction."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: ExtractionWorker | None = None
        self._pack_text = ""
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Title
        title = QLabel("Claude Extraction Pack")
        title.setObjectName("titleLabel")
        root.addWidget(title)

        subtitle = QLabel(
            "Generate a Verbatim Pack from matter folder PDFs for AFCA submission drafting. "
            "Uses Groq AI to intelligently extract relevant passages by document type."
        )
        subtitle.setObjectName("subtitleLabel")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        # Input group
        input_group = QGroupBox("Pack Settings")
        ig = QVBoxLayout(input_group)

        # Folder row
        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel("Folder:"))
        self._folder_edit = QLineEdit()
        self._folder_edit.setPlaceholderText("Select folder containing matter PDFs...")
        folder_row.addWidget(self._folder_edit, 1)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(browse_btn)
        ig.addLayout(folder_row)

        # Matter ref row
        matter_row = QHBoxLayout()
        matter_row.addWidget(QLabel("Matter Ref:"))
        self._matter_edit = QLineEdit()
        self._matter_edit.setPlaceholderText("e.g. MAT-2026-0042")
        matter_row.addWidget(self._matter_edit, 1)
        ig.addLayout(matter_row)

        # Date of loss row
        dol_row = QHBoxLayout()
        dol_row.addWidget(QLabel("Date of Loss:"))
        self._dol_edit = QLineEdit()
        self._dol_edit.setPlaceholderText("DD Month YYYY")
        dol_row.addWidget(self._dol_edit, 1)
        ig.addLayout(dol_row)

        root.addWidget(input_group)

        # Action row
        action_row = QHBoxLayout()
        self._generate_btn = QPushButton("Generate Verbatim Pack")
        self._generate_btn.setObjectName("primaryButton")
        self._generate_btn.clicked.connect(self._start_extraction)
        action_row.addWidget(self._generate_btn)
        action_row.addStretch()
        root.addLayout(action_row)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setTextVisible(True)
        root.addWidget(self._progress)

        # Summary panel
        self._summary_widget = QWidget()
        summary_layout = QHBoxLayout(self._summary_widget)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        self._lbl_docs = QLabel("Documents: 0")
        self._lbl_ai = QLabel("AI-assisted: 0")
        self._lbl_review = QLabel("Manual review: 0")
        self._lbl_vps = QLabel("VP sections: --")
        for lbl in (self._lbl_docs, self._lbl_ai, self._lbl_review, self._lbl_vps):
            lbl.setObjectName("subtitleLabel")
            summary_layout.addWidget(lbl)
        summary_layout.addStretch()
        self._summary_widget.setVisible(False)
        root.addWidget(self._summary_widget)

        # Missing sections warning
        self._missing_label = QLabel()
        self._missing_label.setWordWrap(True)
        self._missing_label.setStyleSheet(
            "padding: 8px; border: 1px solid #f38ba8; border-radius: 4px;"
        )
        self._missing_label.setVisible(False)
        root.addWidget(self._missing_label)

        # Output text area
        self._output = QTextEdit()
        self._output.setReadOnly(True)
        self._output.setPlaceholderText("Verbatim Pack output will appear here...")
        root.addWidget(self._output, 1)

        # Bottom buttons
        bottom_row = QHBoxLayout()
        self._copy_btn = QPushButton("Copy to Clipboard")
        self._copy_btn.setEnabled(False)
        self._copy_btn.clicked.connect(self._copy_to_clipboard)
        bottom_row.addWidget(self._copy_btn)

        self._save_btn = QPushButton("Save as TXT")
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save_as_txt)
        bottom_row.addWidget(self._save_btn)

        bottom_row.addStretch()
        root.addLayout(bottom_row)

    # ---- Slots -----------------------------------------------------------

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Matter Folder", self._folder_edit.text()
        )
        if folder:
            self._folder_edit.setText(folder)

    def _start_extraction(self):
        folder = self._folder_edit.text().strip()
        if not folder or not os.path.isdir(folder):
            QMessageBox.warning(self, "Invalid Folder",
                                "Please select a valid folder containing PDF files.")
            return

        self._output.clear()
        self._pack_text = ""
        self._copy_btn.setEnabled(False)
        self._save_btn.setEnabled(False)
        self._generate_btn.setEnabled(False)
        self._summary_widget.setVisible(False)
        self._missing_label.setVisible(False)

        self._progress.setValue(0)
        self._progress.setVisible(True)

        self._worker = ExtractionWorker(
            folder=folder,
            matter_ref=self._matter_edit.text().strip(),
            date_of_loss=self._dol_edit.text().strip(),
            parent=self,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.status_msg.connect(self._on_status)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, current: int, total: int):
        self._progress.setMaximum(total)
        self._progress.setValue(current)

    def _on_status(self, msg: str):
        self._progress.setFormat(msg)

    def _on_finished(self, pack_text: str, summary: dict):
        self._pack_text = pack_text
        self._output.setPlainText(pack_text)
        self._progress.setFormat("Complete")
        self._generate_btn.setEnabled(True)
        self._copy_btn.setEnabled(True)
        self._save_btn.setEnabled(True)
        self._worker = None

        # Update summary
        total = summary.get("total", 0)
        ai_count = summary.get("ai_count", 0)
        fallback = summary.get("fallback_count", 0)
        vp_pop = summary.get("vp_populated", {})

        self._lbl_docs.setText(f"Documents: {total}")
        self._lbl_ai.setText(f"AI-assisted: {ai_count}")
        self._lbl_review.setText(f"Manual review: {fallback}")

        vp_indicators = []
        missing_vps = []
        for vp in ["VP1", "VP2", "VP3", "VP4", "VP5", "VP6"]:
            if vp_pop.get(vp):
                vp_indicators.append(f"{vp} \u2713")
            else:
                vp_indicators.append(f"{vp} \u2717")
                missing_vps.append(f"{vp} ({VP_SECTIONS.get(vp, vp)})")
        self._lbl_vps.setText("VP: " + "  ".join(vp_indicators))
        self._summary_widget.setVisible(True)

        if missing_vps:
            self._missing_label.setText(
                "Missing VP sections (no matching documents found): " +
                ", ".join(missing_vps) +
                "\nCheck that the matter folder contains all relevant evidence."
            )
            self._missing_label.setVisible(True)

    def _on_error(self, message: str):
        self._progress.setVisible(False)
        self._generate_btn.setEnabled(True)
        QMessageBox.critical(self, "Extraction Error", message)
        self._worker = None

    def _copy_to_clipboard(self):
        if self._pack_text:
            QApplication.clipboard().setText(self._pack_text)
            QMessageBox.information(self, "Copied", "Verbatim Pack copied to clipboard.")

    def _save_as_txt(self):
        if not self._pack_text:
            return
        matter = self._matter_edit.text().strip() or "VerbatimPack"
        default_name = f"{matter}_VerbatimPack.txt"
        folder = self._folder_edit.text().strip()
        default_path = os.path.join(folder, default_name) if folder else default_name

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Verbatim Pack", default_path, "Text Files (*.txt)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._pack_text)
            QMessageBox.information(self, "Saved", f"Verbatim Pack saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save:\n{e}")
