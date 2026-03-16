"""
Duplicate detection service.
Detects exact binary duplicates, content duplicates, and filename collisions.
"""
from typing import Dict, List, Tuple
from collections import defaultdict

from src.core.models import DocumentRecord, DuplicateStatus


def detect_duplicates(records: List[DocumentRecord]) -> List[DocumentRecord]:
    """
    Detect duplicates among records. Modifies records in-place with duplicate_status.
    Returns the modified list.
    """
    # 1. Exact binary duplicates (same file hash)
    hash_groups: Dict[str, List[int]] = defaultdict(list)
    for i, rec in enumerate(records):
        if rec.file_hash:
            hash_groups[rec.file_hash].append(i)

    for file_hash, indices in hash_groups.items():
        if len(indices) > 1:
            for idx in indices:
                records[idx].duplicate_status = DuplicateStatus.EXACT_DUPLICATE

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

    # 3. Filename collisions (same proposed filename)
    name_groups: Dict[str, List[int]] = defaultdict(list)
    for i, rec in enumerate(records):
        if rec.proposed_filename:
            name_groups[rec.proposed_filename.lower()].append(i)

    for name, indices in name_groups.items():
        if len(indices) > 1:
            for idx in indices:
                if records[idx].duplicate_status == DuplicateStatus.NONE:
                    records[idx].duplicate_status = DuplicateStatus.NAME_COLLISION

    return records


def resolve_name_collisions(records: List[DocumentRecord]) -> List[DocumentRecord]:
    """Add (1), (2) suffixes to resolve filename collisions."""
    name_count: Dict[str, int] = defaultdict(int)
    for rec in records:
        key = rec.proposed_filename.lower()
        name_count[key] += 1

    # For names that appear more than once, add suffixes
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
