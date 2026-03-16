"""
Duplicate detection service.
Detects exact binary duplicates, content duplicates, and filename collisions.

Duplicate naming rule:
- First occurrence of a duplicate: renamed normally by convention
- Second, third etc: renamed to just "DUPLICATE.pdf" (or "DUPLICATE (2).pdf" etc)
"""
from typing import Dict, List
from collections import defaultdict

from src.core.models import DocumentRecord, DuplicateStatus


def detect_duplicates(records: List[DocumentRecord]) -> List[DocumentRecord]:
    """
    Detect duplicates among records. Modifies records in-place with duplicate_status.
    First occurrence keeps its proposed filename. Subsequent occurrences are
    renamed to just "DUPLICATE.pdf".
    Returns the modified list.
    """
    # 1. Exact binary duplicates (same file hash)
    hash_groups: Dict[str, List[int]] = defaultdict(list)
    for i, rec in enumerate(records):
        if rec.file_hash:
            hash_groups[rec.file_hash].append(i)

    for file_hash, indices in hash_groups.items():
        if len(indices) > 1:
            # First index keeps its name and status; subsequent get DUPLICATE
            for idx in indices:
                records[idx].duplicate_status = DuplicateStatus.EXACT_DUPLICATE
            for idx in indices[1:]:
                records[idx].proposed_filename = "DUPLICATE.pdf"

    # 2. Content duplicates (same content hash, different file hash)
    content_groups: Dict[str, List[int]] = defaultdict(list)
    for i, rec in enumerate(records):
        if rec.content_hash and rec.duplicate_status == DuplicateStatus.NONE:
            content_groups[rec.content_hash].append(i)

    for content_hash, indices in content_groups.items():
        if len(indices) > 1:
            for idx in indices:
                if records[idx].duplicate_status == DuplicateStatus.NONE:
                    records[idx].duplicate_status = DuplicateStatus.LIKELY_DUPLICATE
            for idx in indices[1:]:
                if records[idx].proposed_filename != "DUPLICATE.pdf":
                    records[idx].proposed_filename = "DUPLICATE.pdf"

    # 3. Filename collisions (same proposed filename, not already DUPLICATE)
    name_groups: Dict[str, List[int]] = defaultdict(list)
    for i, rec in enumerate(records):
        if rec.proposed_filename:
            name_groups[rec.proposed_filename.lower()].append(i)

    for name, indices in name_groups.items():
        if len(indices) > 1:
            for idx in indices:
                if records[idx].duplicate_status == DuplicateStatus.NONE:
                    records[idx].duplicate_status = DuplicateStatus.NAME_COLLISION
            for idx in indices[1:]:
                if records[idx].proposed_filename != "DUPLICATE.pdf":
                    records[idx].proposed_filename = "DUPLICATE.pdf"

    return records


def _append_duplicate(filename: str) -> str:
    """Return 'DUPLICATE.pdf' for duplicate files."""
    return "DUPLICATE.pdf"


def resolve_name_collisions(records: List[DocumentRecord]) -> List[DocumentRecord]:
    """
    After duplicate marking, ensure no two records still share the same
    proposed filename. Any remaining collisions get (2), (3) etc suffixes.
    """
    name_count: Dict[str, int] = defaultdict(int)
    for rec in records:
        key = rec.proposed_filename.lower()
        name_count[key] += 1

    name_index: Dict[str, int] = defaultdict(int)
    for rec in records:
        key = rec.proposed_filename.lower()
        if name_count[key] > 1:
            name_index[key] += 1
            if name_index[key] > 1:
                base = rec.proposed_filename
                if base.lower().endswith(".pdf"):
                    base = base[:-4]
                rec.proposed_filename = f"{base} ({name_index[key]}).pdf"

    return records
