"""
Settings dialog for editing rules, entities, keywords, and preferences.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QTextEdit, QPushButton, QSpinBox,
    QCheckBox, QComboBox, QGroupBox, QFormLayout, QMessageBox
)

from src.core.settings import Settings


class SettingsDialog(QDialog):
    """Settings dialog with tabs for different configuration areas."""

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Settings - Claim File Renamer")
        self.setMinimumSize(700, 600)
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        # General tab
        general = QWidget()
        gl = QFormLayout(general)

        self._dark_mode = QCheckBox("Enable dark mode")
        gl.addRow(self._dark_mode)

        self._confidence_threshold = QSpinBox()
        self._confidence_threshold.setRange(0, 100)
        gl.addRow("UNSURE confidence threshold:", self._confidence_threshold)

        self._strip_annexure = QCheckBox("Strip annexure prefixes by default")
        gl.addRow(self._strip_annexure)

        self._preserve_annexure_meta = QCheckBox("Preserve annexure metadata in audit log")
        gl.addRow(self._preserve_annexure_meta)

        self._photo_mode = QComboBox()
        self._photo_mode.addItems(["conservative", "linked-document"])
        gl.addRow("Photo schedule date mode:", self._photo_mode)

        self._dup_handling = QComboBox()
        self._dup_handling.addItems(["flag_for_review", "keep_both", "skip_duplicates"])
        gl.addRow("Duplicate handling:", self._dup_handling)

        tabs.addTab(general, "General")

        # WHO Mapping tab
        who_tab = QWidget()
        wl = QVBoxLayout(who_tab)
        wl.addWidget(QLabel("Complainant-side entities (one per line):"))
        self._comp_entities = QTextEdit()
        self._comp_entities.setMaximumHeight(100)
        wl.addWidget(self._comp_entities)
        wl.addWidget(QLabel("FF-side entities (one per line):"))
        self._ff_entities = QTextEdit()
        self._ff_entities.setMaximumHeight(100)
        wl.addWidget(self._ff_entities)
        wl.addWidget(QLabel("AFCA entities (one per line):"))
        self._afca_entities = QTextEdit()
        self._afca_entities.setMaximumHeight(100)
        wl.addWidget(self._afca_entities)
        wl.addWidget(QLabel("Complainant keywords (one per line):"))
        self._comp_kw = QTextEdit()
        self._comp_kw.setMaximumHeight(80)
        wl.addWidget(self._comp_kw)
        wl.addWidget(QLabel("FF keywords (one per line):"))
        self._ff_kw = QTextEdit()
        self._ff_kw.setMaximumHeight(80)
        wl.addWidget(self._ff_kw)
        wl.addStretch()
        tabs.addTab(who_tab, "WHO Mapping")

        # Entity Aliases tab
        alias_tab = QWidget()
        al = QVBoxLayout(alias_tab)
        al.addWidget(QLabel("Entity aliases (format: Alias = Preferred Label, one per line):"))
        self._aliases_text = QTextEdit()
        al.addWidget(self._aliases_text)
        al.addWidget(QLabel("Preferred entities (one per line):"))
        self._pref_entities = QTextEdit()
        self._pref_entities.setMaximumHeight(150)
        al.addWidget(self._pref_entities)
        tabs.addTab(alias_tab, "Entities")

        # Document Types tab
        doc_tab = QWidget()
        dl = QVBoxLayout(doc_tab)
        dl.addWidget(QLabel("Preferred document labels (one per line):"))
        self._pref_labels = QTextEdit()
        dl.addWidget(self._pref_labels)
        dl.addWidget(QLabel(
            "Document keyword rules (format: Label = keyword1, keyword2, one per line):"
        ))
        self._doc_keywords = QTextEdit()
        dl.addWidget(self._doc_keywords)
        tabs.addTab(doc_tab, "Document Types")

        # Entity Include Rules tab
        include_tab = QWidget()
        il = QVBoxLayout(include_tab)
        il.addWidget(QLabel(
            "Entity include rules (format: DocType = yes/no, one per line):\n"
            "Controls whether ENTITY is shown in the filename for each document type."
        ))
        self._entity_rules = QTextEdit()
        il.addWidget(self._entity_rules)
        tabs.addTab(include_tab, "Entity Rules")

        layout.addWidget(tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        save_btn = QPushButton("Save")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _load_values(self):
        s = self.settings
        self._dark_mode.setChecked(s.get("dark_mode", True))
        self._confidence_threshold.setValue(s.get("confidence_threshold", 60))
        self._strip_annexure.setChecked(s.get("strip_annexure_prefix", True))
        self._preserve_annexure_meta.setChecked(s.get("preserve_annexure_metadata", True))

        pm = s.get("photo_schedule_date_mode", "conservative")
        idx = self._photo_mode.findText(pm)
        if idx >= 0:
            self._photo_mode.setCurrentIndex(idx)

        dh = s.get("duplicate_handling", "flag_for_review")
        idx = self._dup_handling.findText(dh)
        if idx >= 0:
            self._dup_handling.setCurrentIndex(idx)

        mapping = s.get("who_mapping", {})
        self._comp_entities.setPlainText(
            "\n".join(mapping.get("complainant_entities", []))
        )
        self._ff_entities.setPlainText(
            "\n".join(mapping.get("ff_entities", []))
        )
        self._afca_entities.setPlainText(
            "\n".join(mapping.get("afca_entities", []))
        )
        self._comp_kw.setPlainText(
            "\n".join(mapping.get("complainant_keywords", []))
        )
        self._ff_kw.setPlainText(
            "\n".join(mapping.get("ff_keywords", []))
        )

        aliases = s.get("entity_aliases", {})
        alias_lines = [f"{k} = {v}" for k, v in aliases.items()]
        self._aliases_text.setPlainText("\n".join(alias_lines))

        self._pref_entities.setPlainText(
            "\n".join(s.get("preferred_entities", []))
        )
        self._pref_labels.setPlainText(
            "\n".join(s.get("preferred_doc_labels", []))
        )

        doc_kw = s.get("doc_type_keywords", {})
        kw_lines = [f"{label} = {', '.join(keywords)}" for label, keywords in doc_kw.items()]
        self._doc_keywords.setPlainText("\n".join(kw_lines))

        rules = s.get("entity_include_rules", {})
        rule_lines = [f"{dt} = {'yes' if inc else 'no'}" for dt, inc in rules.items()]
        self._entity_rules.setPlainText("\n".join(rule_lines))

    def _save(self):
        s = self.settings
        s.set("dark_mode", self._dark_mode.isChecked())
        s.set("confidence_threshold", self._confidence_threshold.value())
        s.set("strip_annexure_prefix", self._strip_annexure.isChecked())
        s.set("preserve_annexure_metadata", self._preserve_annexure_meta.isChecked())
        s.set("photo_schedule_date_mode", self._photo_mode.currentText())
        s.set("duplicate_handling", self._dup_handling.currentText())

        mapping = s.get("who_mapping", {})
        mapping["complainant_entities"] = self._lines(self._comp_entities)
        mapping["ff_entities"] = self._lines(self._ff_entities)
        mapping["afca_entities"] = self._lines(self._afca_entities)
        mapping["complainant_keywords"] = self._lines(self._comp_kw)
        mapping["ff_keywords"] = self._lines(self._ff_kw)
        s.set("who_mapping", mapping)

        # Parse aliases
        aliases = {}
        for line in self._aliases_text.toPlainText().strip().split("\n"):
            if "=" in line:
                parts = line.split("=", 1)
                aliases[parts[0].strip()] = parts[1].strip()
        s.set("entity_aliases", aliases)

        s.set("preferred_entities", self._lines(self._pref_entities))
        s.set("preferred_doc_labels", self._lines(self._pref_labels))

        # Parse doc keywords
        doc_kw = {}
        for line in self._doc_keywords.toPlainText().strip().split("\n"):
            if "=" in line:
                parts = line.split("=", 1)
                label = parts[0].strip()
                keywords = [kw.strip() for kw in parts[1].split(",") if kw.strip()]
                doc_kw[label] = keywords
        s.set("doc_type_keywords", doc_kw)

        # Parse entity include rules
        rules = {}
        for line in self._entity_rules.toPlainText().strip().split("\n"):
            if "=" in line:
                parts = line.split("=", 1)
                dt = parts[0].strip()
                val = parts[1].strip().lower()
                rules[dt] = val in ("yes", "true", "1")
        s.set("entity_include_rules", rules)

        s.save()
        QMessageBox.information(self, "Settings", "Settings saved successfully.")
        self.accept()

    def _lines(self, text_edit: QTextEdit) -> list:
        return [
            line.strip() for line in text_edit.toPlainText().strip().split("\n")
            if line.strip()
        ]
