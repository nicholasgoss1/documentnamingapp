"""
Main inference pipeline that orchestrates all engines.
Processes a list of PDF files and produces DocumentRecords.
"""
import os
import re
from typing import List, Callable, Optional

from src.core.models import DocumentRecord, DuplicateStatus
from src.core.settings import Settings
from src.services.pdf_extractor import (
    extract_text, extract_page1_text, extract_page1_spatial,
    compute_file_hash, compute_content_hash
)
from src.services.classifier import (
    detect_annexure, infer_who, infer_entity, infer_what,
    should_include_entity, extract_quote_amount
)
from src.services.date_engine import infer_date
from src.services.normalizer import (
    normalize_entity, normalize_what, normalize_who, clean_filename
)
from src.services.confidence import compute_confidence, should_mark_unsure
from src.services.duplicate_detector import detect_duplicates, resolve_name_collisions


def process_single_file(file_path: str, settings: Settings) -> DocumentRecord:
    """Process a single PDF and return a DocumentRecord with inferred fields."""
    record = DocumentRecord()
    record.file_path = file_path
    record.original_filename = os.path.basename(file_path)

    # Check for annexure
    is_annexure, annex_num = detect_annexure(record.original_filename)
    record.annexure_number = annex_num
    strip_annexure = settings.get("strip_annexure_prefix", True)
    record.annexure_stripped = is_annexure and strip_annexure

    # Extract text
    record.page1_text = extract_page1_text(file_path)
    record.extracted_text = extract_text(file_path, max_pages=5)
    record.page1_regions = extract_page1_spatial(file_path)

    # Compute hashes
    record.file_hash = compute_file_hash(file_path)
    record.content_hash = compute_content_hash(record.extracted_text)

    # Infer ENTITY first (used by WHO inference)
    entity, entity_conf = infer_entity(
        record.page1_text, record.extracted_text,
        record.original_filename, settings, record.page1_regions
    )
    record.entity = normalize_entity(entity, settings)

    # Infer WHO
    who, who_conf = infer_who(
        record.page1_text, record.extracted_text,
        record.original_filename, record.entity, settings,
        record.page1_regions
    )
    record.who = normalize_who(who)

    # Infer WHAT
    what, what_conf = infer_what(
        record.page1_text, record.extracted_text,
        record.original_filename, settings
    )
    record.what = normalize_what(what, settings)

    # Document-type-based WHO overrides
    what_lower = record.what.lower() if record.what else ""

    # Spatial layout regions for letter-format documents.
    page1 = record.page1_text or ""
    page1_lower = page1.lower()
    # Normalize whitespace for phrase matching — PDF extraction preserves
    # line breaks within paragraphs which splits phrases across lines.
    page1_normalized = re.sub(r'\s+', ' ', page1_lower)
    regions = record.page1_regions or {}
    top_right = regions.get("top_right", "").lower()

    # Build entity lookup for from-party detection
    mapping = settings.get("who_mapping", {})
    ff_ents = [e.lower() for e in mapping.get("ff_entities", [])]

    # IDR/FDL documents: determine authorship using spatial layout.
    # Key insight: in letter format, top-right = FROM (letterhead),
    # top-left = TO (addressee).
    #   - If top-right has an FF entity → FROM the insurer → IDR FDL
    #   - If top-left has an FF entity but top-right does NOT → the
    #     letter is addressed TO the insurer → ClaimsCo Letter to IDR
    #   - Fallback: check ClaimsCo authorship phrases in body text
    ff_doc_types = ["idr fdl", "idr", "final decision letter"]
    if any(dt in what_lower for dt in ff_doc_types):
        top_left = regions.get("top_left", "").lower()
        from_has_ff = any(ent in top_right for ent in ff_ents)
        to_has_ff = any(ent in top_left for ent in ff_ents)

        if from_has_ff:
            # Letterhead is an insurer → this IS the insurer's IDR FDL
            record.who = "FF"
        elif to_has_ff and not from_has_ff:
            # Addressed TO the insurer but FROM someone else →
            # complainant-side letter (ClaimsCo Letter to IDR)
            record.who = "Complainant"
            record.what = "ClaimsCo Letter to IDR"
            record.entity = "ClaimsCo"
        else:
            # Fallback: check ClaimsCo authorship phrases
            claimsco_authorship_phrases = [
                "on behalf of our mutual client",
                "on behalf of the below complainant",
                "on behalf of the complainant",
                "submit a complaint on behalf",
                "claims made easy",
                "desired outcome",
                "resolution of claim settlement",
            ]
            is_from_claimsco = (
                "claimsco" in top_right
                or any(phrase in page1_normalized
                       for phrase in claimsco_authorship_phrases)
            )
            if is_from_claimsco:
                record.who = "Complainant"
                record.what = "ClaimsCo Letter to IDR"
                record.entity = "ClaimsCo"
            else:
                record.who = "FF"

    # ClaimsCo-authored non-IDR documents: detect for WHO override
    claimsco_authorship_phrases = [
        "on behalf of our mutual client",
        "on behalf of the below complainant",
        "on behalf of the complainant",
        "submit a complaint on behalf",
        "claims made easy",
        "desired outcome",
        "resolution of claim settlement",
    ]
    is_from_claimsco = (
        "claimsco" in top_right
        or any(phrase in page1_normalized for phrase in claimsco_authorship_phrases)
    )

    # If authored by ClaimsCo, set entity to ClaimsCo (logo may be image-only)
    if is_from_claimsco and record.entity != "ClaimsCo":
        record.entity = "ClaimsCo"

    # Internal documents: timelines, chronologies, file notes are internal work products
    internal_doc_types = ["timeline", "chronology", "file note", "file notes"]
    if any(dt in what_lower for dt in internal_doc_types):
        record.who = "Internal Document"

    # These document types are always complainant-side regardless of issuer
    complainant_doc_types = [
        "certificate of insurance", "policy schedule",
        "letter of engagement", "delegation of authority",
        "agent authority form", "aaf to be signed", "afca submission",
        "pds", "product disclosure statement",
    ]
    if any(dt in what_lower for dt in complainant_doc_types):
        record.who = "Complainant"

    # Letter of Engagement entity is always ClaimsCo
    if "letter of engagement" in what_lower:
        record.entity = "ClaimsCo"

    # Delegation of Authority entity is always DOA
    if "delegation of authority" in what_lower:
        record.entity = "DOA"

    # Agent Authority Form entity is always AAF
    if "agent authority form" in what_lower:
        record.entity = "AAF"

    # Check if ENTITY should be included for this doc type
    if not should_include_entity(record.what, record.entity, settings):
        record.entity = ""

    # Special handling for quotes with amounts
    if record.what and "quote" in record.what.lower():
        amount = extract_quote_amount(record.extracted_text)
        if amount:
            record.what = f"{record.what} - {amount}"

    # Infer DATE
    photo_mode = settings.get("photo_schedule_date_mode", "conservative")
    date, date_conf = infer_date(
        record.what, record.page1_text, record.extracted_text,
        record.original_filename, photo_mode
    )
    record.date = date

    # Compute confidence
    record.confidence_breakdown = compute_confidence(record, settings)
    record.confidence = record.confidence_breakdown.total()

    # Check UNSURE
    record.is_unsure = should_mark_unsure(record.confidence, settings)

    # Build proposed filename
    record.proposed_filename = record.build_proposed_filename()

    return record


def process_batch(file_paths: List[str], settings: Settings,
                  progress_callback: Optional[Callable] = None) -> List[DocumentRecord]:
    """
    Process a batch of PDF files.
    progress_callback(current, total) is called after each file.
    """
    records = []
    total = len(file_paths)

    for i, fp in enumerate(file_paths):
        record = process_single_file(fp, settings)
        records.append(record)
        if progress_callback:
            progress_callback(i + 1, total)

    # Detect duplicates
    records = detect_duplicates(records)

    # Resolve name collisions
    records = resolve_name_collisions(records)

    return records


def reprocess_record(record: DocumentRecord, settings: Settings) -> DocumentRecord:
    """Re-run inference on a single record (e.g., after settings change)."""
    if record.locked:
        return record
    return process_single_file(record.file_path, settings)
