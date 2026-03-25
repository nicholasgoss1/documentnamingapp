"""
Date inference engine with document-type-specific rules.
All processing is local.
"""
import re
from typing import Tuple

# Full and abbreviated month names for regex alternation
_MONTHS_FULL = "January|February|March|April|May|June|July|August|September|October|November|December"
_MONTHS_ABBR = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
_MONTHS_ALL = f"{_MONTHS_FULL}|{_MONTHS_ABBR}"

# Patterns for date extraction
DATE_PATTERNS = [
    # dd/mm/yyyy or dd.mm.yyyy or dd-mm-yyyy
    (r'\b(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})\b', "dmy"),
    # dd/mm/yy or dd.mm.yy or dd-mm-yy (2-digit year)
    (r'\b(\d{1,2})[./\-](\d{1,2})[./\-](\d{2})\b', "dmy2"),
    # yyyy-mm-dd (ISO)
    (r'\b(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})\b', "ymd"),
    # Written dates: 11 April 2024, 11 Apr 2024, April 11, 2024, Apr 11, 2024
    (rf'\b(\d{{1,2}})\s+({_MONTHS_ALL})\s+(\d{{4}})\b', "dMy"),
    (rf'\b({_MONTHS_ALL})\s+(\d{{1,2}}),?\s+(\d{{4}})\b', "Mdy"),
    # mm/yyyy or mm.yyyy (partial) - only match if NOT preceded by digit+separator
    (r'(?<!\d[./\-]\d)(?<!\d[./\-])(\d{1,2})[./\-](\d{4})\b', "my"),
]

MONTH_MAP = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}

# Document types that use specific date rules
LETTER_TYPES = [
    "site report", "assessment report", "building report", "roof report",
    "hail report", "engineering report", "desktop report",
    "final report",
    "progress report", "supplementary report",
    "supplementary technical assessment report", "notice of response",
    "idr fdl", "claims team fdl",
    "request for information", "written preliminary assessment",
    "initial claims advice", "weather pack",
    "response to afca", "variation report"
]
SIGNED_TYPES = ["letter of engagement", "agent authority form", "aaf to be signed", "delegation of authority"]
POLICY_TYPES = ["policy schedule", "certificate of insurance"]
PDS_TYPES = ["pds"]
LODGEMENT_TYPES = ["claim lodgement email", "claim lodgement form"]
QUOTE_TYPES = ["quote"]
PHOTO_TYPES = ["photo schedule"]
INTERNAL_TYPES = ["timeline", "chronology", "file note"]


def _valid_date_parts(d: int = 1, m: int = 1, y: int = 2000) -> bool:
    """Check if date components are reasonable."""
    return 1 <= d <= 31 and 1 <= m <= 12 and 1900 <= y <= 2099


def parse_date(text: str, pattern_type: str, match) -> Tuple[str, bool]:
    """Parse a regex match into dd.mm.yyyy or mm.yyyy. Returns (date_str, is_partial)."""
    if pattern_type == "dmy":
        d, m, y = int(match.group(1)), int(match.group(2)), int(match.group(3))
        if not _valid_date_parts(d, m, y):
            return "", False
        return f"{d:02d}.{m:02d}.{match.group(3)}", False
    elif pattern_type == "dmy2":
        d, m, yy = int(match.group(1)), int(match.group(2)), int(match.group(3))
        # Convert 2-digit year: 00-49 → 2000-2049, 50-99 → 1950-1999
        y = 2000 + yy if yy < 50 else 1900 + yy
        if not _valid_date_parts(d, m, y):
            return "", False
        return f"{d:02d}.{m:02d}.{y}", False
    elif pattern_type == "ymd":
        y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
        if not _valid_date_parts(d, m, y):
            return "", False
        return f"{d:02d}.{m:02d}.{match.group(1)}", False
    elif pattern_type == "dMy":
        d = int(match.group(1))
        m = MONTH_MAP[match.group(2).lower()]
        y = int(match.group(3))
        if not _valid_date_parts(d, int(m), y):
            return "", False
        return f"{d:02d}.{m}.{match.group(3)}", False
    elif pattern_type == "Mdy":
        m = MONTH_MAP[match.group(1).lower()]
        d = int(match.group(2))
        y = int(match.group(3))
        if not _valid_date_parts(d, int(m), y):
            return "", False
        return f"{d:02d}.{m}.{match.group(3)}", False
    elif pattern_type == "my":
        m, y = int(match.group(1)), int(match.group(2))
        if not (1 <= m <= 12 and 1900 <= y <= 2099):
            return "", False
        return f"{m:02d}.{match.group(2)}", True
    return "", False


# Labels that introduce a non-letter date (e.g. "Date of Loss: 24 Dec 2023").
# Dates following these labels describe the event, NOT the document date.
_EVENT_DATE_LABELS = re.compile(
    r'(?:date\s+of\s+(?:loss|incident|event|damage|claim|notification|inspection)|'
    r'date\s+(?:notified|reported|lodged)|'
    r'incident\s+date|loss\s+date|event\s+date|inspection\s+date|'
    r'effective\s+date|effective\s+from|'
    r'originally\s+constructed|constructed\s+in)\s*[:.]?\s*$',
    re.IGNORECASE,
)


def extract_all_dates(text: str, exclude_event_dates: bool = False) -> list:
    """Extract all date candidates from text. Returns list of (date_str, is_partial, position).

    If exclude_event_dates is True, dates immediately preceded by labels like
    "Date of Loss:", "Date of Incident:", "Incident date:" are skipped.
    """
    results = []
    for pattern, ptype in DATE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            date_str, is_partial = parse_date(text, ptype, match)
            if not date_str:
                continue
            # Optionally skip event/loss dates
            if exclude_event_dates:
                prefix = text[max(0, match.start() - 60):match.start()]
                if _EVENT_DATE_LABELS.search(prefix):
                    continue
            results.append((date_str, is_partial, match.start()))
    # Sort by position in text so earliest date comes first regardless of
    # which regex pattern matched it.
    results.sort(key=lambda x: x[2])
    return results


def _date_year(date_str: str) -> int:
    """Extract the year from a date string like '26.07.2024' or '07.2024'."""
    parts = date_str.split('.')
    try:
        return int(parts[-1])
    except (ValueError, IndexError):
        return 0


def find_page1_top_date(page1_text: str, exclude_event_dates: bool = False) -> Tuple[str, bool]:
    """Find the first date in the top portion of page 1."""
    # Consider the top ~40 lines or first 2000 chars
    top_text = page1_text[:2000]
    dates = extract_all_dates(top_text, exclude_event_dates=exclude_event_dates)
    if dates:
        return dates[0][0], dates[0][1]
    return "", False


def find_signed_date(text: str) -> str:
    """Look for a signature/execution date."""
    # Look for patterns like "Date signed:", "Signed:", "Executed:" near signature blocks
    # Also match standalone "Date:" which is common in signature blocks
    patterns = [
        r'(?:date\s+signed|signed|executed|date\s+of\s+signing)\s*[:.]?\s*(\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4})',
        r'(?:date\s+signed|signed|executed|date\s+of\s+signing)\s*[:.]?\s*(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            # Re-extract the date from the match
            sub_dates = extract_all_dates(m.group(0))
            if sub_dates:
                return sub_dates[0][0]

    # Check for standalone "Date:" in the last portion of the document
    # (signature blocks are typically near the end)
    tail = text[-1500:] if len(text) > 1500 else text
    date_label_patterns = [
        r'\bDate\s*[:.]?\s*(\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4})',
    ]
    # Find the LAST "Date:" match in the tail (closest to signature)
    last_match = None
    for pat in date_label_patterns:
        for m in re.finditer(pat, tail, re.IGNORECASE):
            last_match = m
    if last_match:
        sub_dates = extract_all_dates(last_match.group(0))
        if sub_dates:
            return sub_dates[0][0]

    return ""


def find_printed_on_date(text: str) -> str:
    """Look for 'Printed On: DD/MM/YYYY' pattern common in site reports."""
    patterns = [
        r'[Pp]rinted\s+[Oo]n\s*[:.]?\s*(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})',
        r'[Pp]rinted\s+[Oo]n\s*[:.]?\s*(\d{1,2}\s+(?:' + _MONTHS_ALL + r')\s+\d{4})',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            sub_dates = extract_all_dates(m.group(0))
            if sub_dates:
                return sub_dates[0][0]
    return ""


def find_policy_inception_date(text: str) -> str:
    """Look for policy inception / effective-from date."""
    patterns = [
        r'(?:inception\s+date|inception|effective\s+(?:from|date)|period\s+(?:from|of\s+insurance\s+from)|commencement)\s*[:.]?\s*(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})',
        r'(?:inception\s+date|inception|effective\s+(?:from|date)|period\s+from|commencement)\s*[:.]?\s*(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            sub_dates = extract_all_dates(m.group(0))
            if sub_dates:
                return sub_dates[0][0]
    return ""


def find_pds_edition_date(text: str, filename: str) -> str:
    """Look for PDS edition / wording code date (partial mm.yyyy)."""
    # Check filename for wording codes like QM486-0323
    wording_pat = r'([A-Z]{2}\d{3}[-.]?\d{4})'
    m = re.search(wording_pat, filename, re.IGNORECASE)
    if m:
        code = m.group(1)
        # Try to extract mm.yyyy from the code
        digits = re.search(r'(\d{2})(\d{2})$', code.replace("-", "").replace(".", ""))
        if digits:
            mm, yy = digits.group(1), digits.group(2)
            if 1 <= int(mm) <= 12:
                return f"{mm}.20{yy}"

    # Look for partial dates in text
    dates = extract_all_dates(text)
    for date_str, is_partial, _ in dates:
        if is_partial:
            return date_str
    # Fall back to any date
    if dates:
        return dates[0][0]
    return "NO DATE"


def infer_date(doc_type: str, page1_text: str, full_text: str,
               filename: str, photo_mode: str = "conservative") -> Tuple[str, int]:
    """
    Infer the best date for a document based on type-specific rules.
    Returns (date_string, confidence_contribution).

    confidence_contribution: 0-20 points for date clarity.
    """
    doc_lower = doc_type.lower() if doc_type else ""

    # 0. Site reports: prefer "Printed On" date (most reliable for these)
    site_report_types = ["site report"]
    if any(t in doc_lower for t in site_report_types):
        printed_date = find_printed_on_date(full_text)
        if printed_date:
            return printed_date, 18
        # Fall through to letter logic if no "Printed On" date

    # 1. Formal letters and reports
    if any(t in doc_lower for t in LETTER_TYPES):
        # Look for the letter date, excluding event dates (Date of Loss etc.)
        date, is_partial = find_page1_top_date(page1_text, exclude_event_dates=True)
        if date and _date_year(date) >= 2000:
            return date, 18 if not is_partial else 12
        # If page 1 date is missing or too old (cover page), check full text
        # (the actual letter date is often on page 2 for reports with cover pages)
        dates = extract_all_dates(full_text[:6000], exclude_event_dates=True)
        recent = [d for d in dates if _date_year(d[0]) >= 2000]
        if recent:
            return recent[0][0], 16 if not recent[0][1] else 10
        # Check for "Printed on DD/MM/YYYY" (common in site reports at bottom)
        printed_date = find_printed_on_date(full_text)
        if printed_date:
            return printed_date, 16
        # fallback: any date in full text (including event dates)
        dates = extract_all_dates(full_text)
        if dates:
            return dates[0][0], 8
        return "NO DATE", 5

    # 2. Signed documents — date can be on ANY page (e.g. client signs page 4)
    if any(t in doc_lower for t in SIGNED_TYPES):
        # Best case: explicit "Date signed:" / "Signed:" / "Executed:" label
        signed = find_signed_date(full_text)
        if signed:
            return signed, 18
        # Scan the entire document for any date (last found is likely the
        # signing date since signatures are typically near the end)
        all_dates = extract_all_dates(full_text)
        if all_dates:
            return all_dates[-1][0], 14
        return "NO DATE", 5

    # 3. Policy schedule / COI
    # Prefer the letter date at the top of page 1 (e.g. endorsement letters).
    # Fall back to policy inception date if no letter date is found.
    if any(t in doc_lower for t in POLICY_TYPES):
        date, is_partial = find_page1_top_date(page1_text, exclude_event_dates=True)
        if date and not is_partial:
            return date, 18
        inception = find_policy_inception_date(full_text)
        if inception:
            return inception, 15
        if date:
            return date, 10
        return "NO DATE", 5

    # 4. PDS
    if any(t in doc_lower for t in PDS_TYPES):
        edition = find_pds_edition_date(full_text, filename)
        if edition and edition != "NO DATE":
            return edition, 15
        return "NO DATE", 5

    # 5. Lodgement materials
    if any(t in doc_lower for t in LODGEMENT_TYPES):
        date, _ = find_page1_top_date(page1_text)
        if date:
            return date, 15
        return "NO DATE", 5

    # 6. Quotes
    if any(t in doc_lower for t in QUOTE_TYPES):
        # Prefer "Printed On" date (common in scope of works / quotes)
        printed_date = find_printed_on_date(full_text)
        if printed_date:
            return printed_date, 18
        # Look for "quote date" or "date" near top
        date, _ = find_page1_top_date(page1_text)
        if date:
            return date, 15
        return "NO DATE", 5

    # 7. Photo schedules
    if any(t in doc_lower for t in PHOTO_TYPES):
        if photo_mode == "conservative":
            date, _ = find_page1_top_date(page1_text)
            if date:
                return date, 12
            return "NO DATE", 5
        else:
            date, _ = find_page1_top_date(page1_text)
            if date:
                return date, 10
            return "NO DATE", 3

    # 8. Internal documents (timelines, chronologies, file notes)
    if any(t in doc_lower for t in INTERNAL_TYPES):
        date, is_partial = find_page1_top_date(page1_text)
        if date:
            return date, 15
        return "NO DATE", 5

    # 9. Weather documents
    if "weather" in doc_lower:
        date, _ = find_page1_top_date(page1_text)
        if date:
            return date, 15
        return "NO DATE", 5

    # Default: use first date found on page 1
    date, is_partial = find_page1_top_date(page1_text)
    if date:
        return date, 12 if not is_partial else 8
    # Try full text
    dates = extract_all_dates(full_text)
    if dates:
        return dates[0][0], 6
    return "NO DATE", 3


def normalize_date(date_str: str) -> str:
    """Normalize a date string to dd.mm.yyyy or mm.yyyy format."""
    if not date_str or date_str == "NO DATE":
        return date_str

    # Fix NOT DATE -> NO DATE
    if date_str.upper().strip() in ("NOT DATE", "NODATE"):
        return "NO DATE"

    # Try to parse and re-format
    dates = extract_all_dates(date_str)
    if dates:
        return dates[0][0]

    return date_str
