"""
Duplicate detection service.
Detects exact binary duplicates, content duplicates, field-based duplicates,
and filename collisions.

Duplicate naming rule:
- First occurrence of a duplicate: renamed normally by convention
- Second, third etc: renamed to just "DUPLICATE.pdf" (or "DUPLICATE (2).pdf" etc)
"""
import re
from typing import Dict, List
from collections import defaultdict

from src.core.models import DocumentRecord, DuplicateStatus


def _normalize_what_for_comparison(what: str) -> str:
    """Normalize a WHAT field for duplicate comparison.
    Strips noise words like 'DUPLICATE', trailing numbers, and extra whitespace."""
    if not what:
        return ""
    s = what.lower()
    # Remove "duplicate" and variations
    s = re.sub(r'\bduplicate\b', '', s, flags=re.IGNORECASE)
    # Remove trailing numbers/suffixes like " 1", " (2)"
    s = re.sub(r'\s*\(\d+\)\s*$', '', s)
    s = re.sub(r'\s+\d+\s*$', '', s)
    return s.strip()


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

    # 3. Field-based duplicates (same WHO+DATE+ENTITY and similar WHAT)
    # Catches cases where files are different PDFs of the same document
    # (e.g. one filename contains "DUPLICATE" or a copy number).
    # Only compare records that have at least WHO and WHAT populated.
    # IMPORTANT: include ALL records in field groups (even already-flagged
    # ones) so a new record with the same fields as an already-flagged
    # exact duplicate also gets caught. Only CHANGE status on NONE records.
    field_groups: Dict[str, List[int]] = defaultdict(list)
    for i, rec in enumerate(records):
        what_norm = _normalize_what_for_comparison(rec.what)
        if not rec.who and not what_norm:
            continue  # Skip records with no meaningful fields to compare
        # Skip records whose fields are literally "DUPLICATE"
        if (rec.who or "").upper() == "DUPLICATE":
            continue
        key = f"{(rec.who or '').lower()}|{(rec.date or '').lower()}|{(rec.entity or '').lower()}|{what_norm}"
        field_groups[key].append(i)

    for key, indices in field_groups.items():
        if len(indices) > 1:
            for idx in indices:
                if records[idx].duplicate_status == DuplicateStatus.NONE:
                    records[idx].duplicate_status = DuplicateStatus.LIKELY_DUPLICATE
            for idx in indices[1:]:
                if records[idx].proposed_filename != "DUPLICATE.pdf":
                    records[idx].proposed_filename = "DUPLICATE.pdf"

    # 3b. One-per-claim document types: same WHO+ENTITY+WHAT regardless of date.
    # Some document types (e.g. Delegation of Authority, Letter of Engagement)
    # should only appear once per claim — duplicates with different dates are
    # likely the same document re-signed or re-scanned.
    ONE_PER_CLAIM_TYPES = [
        "delegation of authority", "letter of engagement",
        "agent authority form", "aaf to be signed", "authority and access form",
    ]
    one_per_claim_groups: Dict[str, List[int]] = defaultdict(list)
    for i, rec in enumerate(records):
        what_norm = _normalize_what_for_comparison(rec.what)
        if not any(t in what_norm for t in ONE_PER_CLAIM_TYPES):
            continue
        key = f"{(rec.who or '').lower()}|{(rec.entity or '').lower()}|{what_norm}"
        one_per_claim_groups[key].append(i)

    for key, indices in one_per_claim_groups.items():
        if len(indices) > 1:
            for idx in indices:
                if records[idx].duplicate_status == DuplicateStatus.NONE:
                    records[idx].duplicate_status = DuplicateStatus.LIKELY_DUPLICATE
            for idx in indices[1:]:
                if records[idx].proposed_filename != "DUPLICATE.pdf":
                    records[idx].proposed_filename = "DUPLICATE.pdf"

    # 4. Filename collisions (same proposed filename, not already DUPLICATE)
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

    # 5. Catch-all: rows whose fields literally contain "DUPLICATE"
    # These are files from a previous session that were renamed to
    # "DUPLICATE.pdf" and then reloaded. Flag them so the user knows
    # they need attention.
    for i, rec in enumerate(records):
        if rec.duplicate_status != DuplicateStatus.NONE:
            continue
        dup_fields = sum(
            1 for v in [rec.who, rec.date, rec.entity, rec.what]
            if v and v.upper() == "DUPLICATE"
        )
        if dup_fields >= 2:
            rec.duplicate_status = DuplicateStatus.LIKELY_DUPLICATE
            rec.proposed_filename = "DUPLICATE.pdf"

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
