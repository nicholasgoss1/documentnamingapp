"""
Data models for the document naming application.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Who(Enum):
    FF = "FF"
    COMPLAINANT = "Complainant"
    AFCA = "AFCA"
    UNKNOWN = "UNKNOWN"


class DuplicateStatus(Enum):
    NONE = "None"
    EXACT_DUPLICATE = "Exact Duplicate"
    LIKELY_DUPLICATE = "Likely Duplicate"
    NAME_COLLISION = "Name Collision"


class RenameStatus(Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    RENAMED = "Renamed"
    SKIPPED = "Skipped"
    ERROR = "Error"
    UNDONE = "Undone"


@dataclass
class ConfidenceBreakdown:
    """Tracks reasons for confidence score."""
    heading_match: int = 0
    date_clarity: int = 0
    entity_match: int = 0
    doc_type_match: int = 0
    date_rule_clarity: int = 0
    filename_consistency: int = 0
    penalties: list = field(default_factory=list)

    def total(self) -> int:
        base = (
            self.heading_match
            + self.date_clarity
            + self.entity_match
            + self.doc_type_match
            + self.date_rule_clarity
            + self.filename_consistency
        )
        penalty = sum(p[1] for p in self.penalties)
        return max(0, min(100, base - penalty))

    def reasons(self) -> str:
        parts = []
        if self.heading_match > 0:
            parts.append(f"Heading match: +{self.heading_match}")
        if self.date_clarity > 0:
            parts.append(f"Date clarity: +{self.date_clarity}")
        if self.entity_match > 0:
            parts.append(f"Entity match: +{self.entity_match}")
        if self.doc_type_match > 0:
            parts.append(f"Doc type match: +{self.doc_type_match}")
        if self.date_rule_clarity > 0:
            parts.append(f"Date rule clarity: +{self.date_rule_clarity}")
        if self.filename_consistency > 0:
            parts.append(f"Filename consistency: +{self.filename_consistency}")
        for reason, amount in self.penalties:
            parts.append(f"{reason}: -{amount}")
        return "; ".join(parts) if parts else "No analysis"


@dataclass
class DocumentRecord:
    """Represents a single PDF document being processed."""
    file_path: str = ""
    original_filename: str = ""
    who: str = ""
    date: str = ""
    entity: str = ""
    what: str = ""
    proposed_filename: str = ""
    confidence: int = 0
    confidence_breakdown: ConfidenceBreakdown = field(default_factory=ConfidenceBreakdown)
    duplicate_status: DuplicateStatus = DuplicateStatus.NONE
    rename_status: RenameStatus = RenameStatus.PENDING
    extracted_text: str = ""
    page1_text: str = ""
    file_hash: str = ""
    content_hash: str = ""
    annexure_number: str = ""
    annexure_stripped: bool = False
    is_unsure: bool = False
    locked: bool = False
    new_file_path: str = ""
    error_message: str = ""

    def build_proposed_filename(self) -> str:
        """Build the proposed filename from components."""
        parts = []
        if self.who:
            parts.append(self.who)
        if self.date:
            parts.append(self.date)
        if self.entity:
            parts.append(self.entity)
        if self.what:
            parts.append(self.what)
        if self.is_unsure:
            parts.append("UNSURE")
        name = " - ".join(parts)
        if not name:
            name = self.original_filename
        if name.lower().endswith(".pdf"):
            name = name[:-4]
        name = sanitize_filename(name)
        return name + ".pdf"


def sanitize_filename(name: str) -> str:
    """Remove invalid Windows filename characters and clean up."""
    invalid_chars = '<>:"/\\|?*'
    for ch in invalid_chars:
        name = name.replace(ch, "")
    # Strip duplicate spaces
    while "  " in name:
        name = name.replace("  ", " ")
    # Strip leading/trailing separators and whitespace
    name = name.strip(" -.")
    # Remove .pdf if present (caller adds it back)
    if name.lower().endswith(".pdf"):
        name = name[:-4].strip(" -.")
    return name
