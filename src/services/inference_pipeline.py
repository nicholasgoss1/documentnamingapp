"""
Main inference pipeline that orchestrates all engines.
Processes a list of PDF files and produces DocumentRecords.
"""
import os
from typing import List, Callable, Optional

from src.core.models import DocumentRecord, DuplicateStatus
from src.core.settings import Settings
from src.services.pdf_extractor import (
    extract_text, extract_page1_text, compute_file_hash, compute_content_hash
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

    # Compute hashes
    record.file_hash = compute_file_hash(file_path)
    record.content_hash = compute_content_hash(record.extracted_text)

    # Infer ENTITY first (used by WHO inference)
    entity, entity_conf = infer_entity(
        record.page1_text, record.extracted_text,
        record.original_filename, settings
    )
    record.entity = normalize_entity(entity, settings)

    # Infer WHO
    who, who_conf = infer_who(
        record.page1_text, record.extracted_text,
        record.original_filename, record.entity, settings
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

    # Detect if the document is authored BY ClaimsCo:
    # ClaimsCo documents have the logo at the top of page 1 and/or a
    # signature block at the bottom.  Insurer IDR responses may mention
    # "ClaimsCo" in the *body* text (e.g. "Dear ClaimsCo"), so we only
    # check the header area (first 1000 chars) and footer/signature area
    # (last 500 chars) of page 1, not the middle body text.
    # PDF text extraction order varies (a right-side logo can appear after
    # left-side address text), so we use a generous header window.
    # When the ClaimsCo logo is an image (not extractable text), we fall
    # back to distinctive authorship phrases that only appear in letters
    # written BY ClaimsCo on behalf of the complainant.
    page1 = record.page1_text or ""
    page1_lower = page1.lower()
    page1_header = page1_lower[:1000]
    page1_footer = page1_lower[-500:] if len(page1_lower) > 500 else ""
    entity_lower = record.entity.lower() if record.entity else ""
    claimsco_authorship_phrases = [
        "on behalf of our mutual client",
        "claims made easy",
        "delegation of authority for the above claim",
    ]
    is_from_claimsco = (
        "claimsco" in page1_header
        or "claimsco" in page1_footer
        or "claimsco" in entity_lower
        or any(phrase in page1_lower for phrase in claimsco_authorship_phrases)
    )

    # IDR/FDL documents are from the Financial Firm — UNLESS authored by
    # ClaimsCo (who writes to the insurer's IDR team on behalf of the
    # complainant, identifiable by either ClaimsCo logo or signature).
    ff_doc_types = ["idr fdl", "idr", "final decision letter"]
    if any(dt in what_lower for dt in ff_doc_types):
        if is_from_claimsco:
            record.who = "Complainant"
            record.what = "ClaimsCo Letter to IDR"
        else:
            record.who = "FF"

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
