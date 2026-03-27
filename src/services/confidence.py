"""
Confidence scoring engine.
Computes a confidence score and breakdown for each document record.
"""
from src.core.models import DocumentRecord, ConfidenceBreakdown
from src.core.settings import Settings


def compute_confidence(record: DocumentRecord, settings: Settings) -> ConfidenceBreakdown:
    """Compute confidence score for a document record."""
    breakdown = ConfidenceBreakdown()

    page1 = record.page1_text.lower() if record.page1_text else ""
    fname = record.original_filename.lower()

    # 1. Heading match (0-20)
    if record.what:
        what_lower = record.what.lower()
        if what_lower in page1[:500]:
            breakdown.heading_match = 20
        elif what_lower in page1:
            breakdown.heading_match = 15
        elif what_lower in fname:
            breakdown.heading_match = 10
        else:
            breakdown.heading_match = 5

    # 2. Date clarity (0-20)
    if record.date and record.date != "NO DATE":
        # Full date
        if len(record.date) == 10:  # dd.mm.yyyy
            breakdown.date_clarity = 18
        else:
            breakdown.date_clarity = 12  # Partial date
    elif record.date == "NO DATE":
        breakdown.date_clarity = 5

    # 3. Entity match (0-15)
    if record.entity:
        entity_lower = record.entity.lower()
        preferred = settings.get("preferred_entities", [])
        if any(entity_lower == p.lower() for p in preferred):
            breakdown.entity_match = 15
        else:
            breakdown.entity_match = 8
    else:
        # Entity is optional, so no entity isn't necessarily bad
        breakdown.entity_match = 5

    # 4. Doc type match (0-20)
    if record.what:
        preferred_labels = settings.get("preferred_doc_labels", [])
        if record.what in preferred_labels:
            breakdown.doc_type_match = 20
        else:
            breakdown.doc_type_match = 10

    # 5. Date rule clarity (0-15)
    if record.date and record.date != "NO DATE":
        breakdown.date_rule_clarity = 15
    else:
        breakdown.date_rule_clarity = 3

    # 6. Filename consistency (0-10)
    if record.who and record.what:
        breakdown.filename_consistency = 10
    elif record.who or record.what:
        breakdown.filename_consistency = 5

    # Penalties
    if not record.what:
        breakdown.penalties.append(("No document type identified", 25))
    if not record.who or record.who == "UNKNOWN":
        breakdown.penalties.append(("No WHO identified", 20))
    if record.annexure_stripped:
        breakdown.penalties.append(("Annexure wrapper filename", 10))
    if not record.page1_text or len(record.page1_text.strip()) < 50:
        breakdown.penalties.append(("Little or no text extracted", 20))
    if record.date == "NO DATE" and record.what:
        # Check if this doc type usually has dates
        dateless_types = {"photo schedule", "quote", "aaf to be signed"}
        if record.what.lower() not in dateless_types:
            breakdown.penalties.append(("Expected date not found", 10))

    # Multiple possible dates penalty
    if record.page1_text:
        from src.services.date_engine import extract_all_dates
        dates = extract_all_dates(record.page1_text)
        if len(dates) > 3:
            breakdown.penalties.append(("Multiple ambiguous dates found", 10))

    return breakdown


def should_mark_unsure(confidence: int, settings: Settings) -> bool:
    """Check if confidence is below threshold for UNSURE marking."""
    threshold = settings.get("confidence_threshold", 60)
    return confidence < threshold
