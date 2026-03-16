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

    # IDR/FDL documents: determine authorship by checking for ClaimsCo
    # authorship phrases FIRST (definitive — an insurer's IDR FDL would
    # never say "on behalf of our mutual client"), then fall back to
    # spatial layout.  We check phrases first because ClaimsCo's logo is
    # often an image (not OCR-extractable), and the addressee text (e.g.
    # "Allianz Insurance") can end up in the top-right region depending
    # on the letter layout.
    ff_doc_types = ["idr fdl", "idr", "final decision letter"]
    if any(dt in what_lower for dt in ff_doc_types):
        claimsco_authorship_phrases = [
            "on behalf of our mutual client",
            "claims made easy",
        ]
        # DEBUG: temporary print to diagnose ClaimsCo detection
        print(f"[DEBUG IDR CHECK] file={record.original_filename}")
        print(f"  what_lower={what_lower!r}")
        print(f"  top_right={top_right!r}")
        print(f"  'claimsco' in top_right = {'claimsco' in top_right}")
        for phrase in claimsco_authorship_phrases:
            print(f"  {phrase!r} in page1_normalized = {phrase in page1_normalized}")
        print(f"  page1_normalized[:500]={page1_normalized[:500]!r}")
        is_from_claimsco = (
            "claimsco" in top_right
            or any(phrase in page1_normalized for phrase in claimsco_authorship_phrases)
        )
        print(f"  is_from_claimsco={is_from_claimsco}")
        if is_from_claimsco:
            record.who = "Complainant"
            record.what = "ClaimsCo Letter to IDR"
        else:
            record.who = "FF"

    # ClaimsCo-authored non-IDR documents: detect for WHO override
    claimsco_authorship_phrases = [
        "on behalf of our mutual client",
        "claims made easy",
    ]
    is_from_claimsco = (
        "claimsco" in top_right
        or any(phrase in page1_normalized for phrase in claimsco_authorship_phrases)
    )

    # These document types are always complainant-side regardless of issuer
    complainant_doc_types = [
        "certificate of insurance", "letter of engagement",
        "aaf to be signed", "afca submission",
    ]
    if any(dt in what_lower for dt in complainant_doc_types):
        record.who = "Complainant"

    # COI entity should be "COI" not the insurer
    if "certificate of insurance" in what_lower:
        record.entity = "COI"

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
