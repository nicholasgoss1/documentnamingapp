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
    extract_page1_rawtext,
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
    record.extracted_text = extract_text(file_path, max_pages=10)
    record.page1_regions = extract_page1_spatial(file_path)

    # Compute hashes
    record.file_hash = compute_file_hash(file_path)
    record.content_hash = compute_content_hash(record.extracted_text)

    # Infer ENTITY first (used by WHO inference)
    entity, entity_conf = infer_entity(
        record.page1_text, record.extracted_text,
        record.original_filename, settings, record.page1_regions
    )
    # If no entity found in first 10 pages, do a deeper scan (up to 30 pages)
    if not entity:
        deep_text = extract_text(file_path, max_pages=30)
        entity, entity_conf = infer_entity(
            record.page1_text, deep_text,
            record.original_filename, settings, record.page1_regions
        )
    # Last resort: word-level extraction captures text that standard
    # extraction misses (unusual font encodings, ligatures, etc.)
    if not entity:
        raw_text = extract_page1_rawtext(file_path)
        if raw_text:
            entity, entity_conf = infer_entity(
                raw_text, raw_text,
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
    ff_doc_types = ["idr fdl", "idr", "final decision letter", "claims team fdl"]
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
                # Entity may have been misidentified (e.g. complainant entity
                # found in signature when the actual author is an insurer).
                # Re-check: if current entity is a complainant entity, look
                # for an FF entity in the text instead.
                comp_ents = [e.lower() for e in mapping.get("complainant_entities", [])]
                if record.entity.lower() in comp_ents:
                    # Search for FF entities in the full text
                    for ent_name in mapping.get("ff_entities", []):
                        if ent_name.lower() in page1_lower or ent_name.lower() in (record.extracted_text or "").lower():
                            record.entity = normalize_entity(ent_name, settings)
                            break

    # ClaimsCo-authored non-IDR documents: detect for WHO override
    claimsco_authorship_phrases = [
        "on behalf of our mutual client",
        "on behalf of the below complainant",
        "on behalf of the complainant",
        "submit a complaint on behalf",
        "claims made easy",
        "desired outcome",
        "resolution of claim settlement",
        "the financial firm's",
    ]
    # If the letterhead (top-right) clearly shows an FF entity, the document
    # is FROM the insurer — body text may reference ClaimsCo without being
    # authored by them.
    letterhead_is_ff = any(ent in top_right for ent in ff_ents)
    is_from_claimsco = (
        not letterhead_is_ff
        and (
            "claimsco" in top_right
            or any(phrase in page1_normalized for phrase in claimsco_authorship_phrases)
        )
    )

    # If authored by ClaimsCo and addressed to/about AFCA, it's a ClaimsCo Letter to IDR
    # (catches cases like "AFCA Re-Lodgement" that mention "hail damage" in the body
    #  and get misclassified as "Hail Report" by keyword matching)
    if is_from_claimsco:
        top_left = regions.get("top_left", "").lower()
        filename_lower = record.original_filename.lower()
        afca_indicators = [
            "afca" in top_left,
            "australian financial complaints authority" in page1_normalized,
            "afca" in filename_lower,
            "afca case number" in page1_normalized,
        ]
        if any(afca_indicators) and what_lower not in ["claimsco letter to idr"]:
            record.who = "Complainant"
            record.entity = "ClaimsCo"
            # Notice of Response from ClaimsCo to AFCA → Response to AFCA
            if "notice of response" in what_lower:
                record.what = "Response to AFCA"
                what_lower = record.what.lower()
            # AFCA Submission: complaint lodgement with AFCA
            elif ("afca submission" in what_lower
                  or "submit a complaint" in page1_normalized
                  or "lodge a complaint" in page1_normalized
                  or "lodgement of a formal complaint" in page1_normalized
                  or "escalate this matter" in page1_normalized):
                record.what = "Submission to AFCA"
                what_lower = record.what.lower()
            else:
                record.what = "ClaimsCo Letter to IDR"

    # If authored by ClaimsCo, set entity to ClaimsCo (logo may be image-only)
    if is_from_claimsco and record.entity != "ClaimsCo":
        record.entity = "ClaimsCo"

    # Notice of Response from an FF entity (e.g. Allianz responding to AFCA)
    # is actually a "Response to AFCA", not AFCA's notice.
    if "notice of response" in what_lower:
        entity_lower = (record.entity or "").lower()
        if letterhead_is_ff or entity_lower in ff_ents:
            record.what = "Response to AFCA"
            record.who = "FF"
            what_lower = record.what.lower()

    # Engineering reports are always FF-side (prepared by engineering firms
    # engaged by the insurer/loss adjuster, not the complainant)
    if "engineering report" in what_lower:
        record.who = "FF"

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
        "pre purchase inspection report",
    ]
    if any(dt in what_lower for dt in complainant_doc_types):
        record.who = "Complainant"

    # Check if ENTITY should be included for this doc type
    if not should_include_entity(record.what, record.entity, settings):
        record.entity = ""

    # Forced entity overrides — these MUST run after should_include_entity
    # so they are never cleared by user settings.
    if "letter of engagement" in what_lower:
        record.entity = "ClaimsCo"
    if "delegation of authority" in what_lower:
        record.entity = "DOA"
    if "agent authority form" in what_lower:
        record.entity = "AAF"
    if "tb32 technical bulletin" in what_lower:
        record.entity = "BlueScope"

    # Patcol documents are always Engineers Roof Reports
    entity_lower_check = (record.entity or "").lower()
    if entity_lower_check == "patcol":
        record.what = "Engineers Roof Report"
        what_lower = record.what.lower()

    # Written Preliminary Assessments are always AFCA-issued documents
    if "written preliminary assessment" in what_lower or "preliminary assessment" in what_lower:
        record.who = "AFCA"
        record.entity = "AFCA"

    # AFCA-authored documents should always show ENTITY = AFCA
    if record.who == "AFCA" and not record.entity:
        record.entity = "AFCA"

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

    # ── Groq AI classification for low-confidence documents ──────────
    if record.confidence < 85:
        try:
            from src.services.ai_classifier import groq_classifier
            if groq_classifier.is_available():
                ai_result = groq_classifier.classify_document(
                    record.extracted_text, filename=record.original_filename
                )
                if ai_result:
                    # Override fields with AI results, running through normalizers
                    if ai_result.get("who"):
                        record.who = normalize_who(ai_result["who"])
                    if ai_result.get("entity"):
                        record.entity = normalize_entity(ai_result["entity"], settings)
                    if ai_result.get("what"):
                        record.what = normalize_what(ai_result["what"], settings)
                    if ai_result.get("date") and ai_result["date"] != "NO DATE":
                        record.date = ai_result["date"]
                    # Boost confidence
                    record.confidence = min(99, record.confidence + 15)
                    record.confidence_breakdown.penalties.append(("ai_groq", -15))
        except Exception:
            pass  # Never crash pipeline due to AI failure

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
