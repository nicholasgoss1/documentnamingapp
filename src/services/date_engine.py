"""
Date inference engine with document-type-specific rules.
All processing is local.
"""
import re
from typing import Tuple

# Patterns for date extraction
DATE_PATTERNS = [
    # dd/mm/yyyy or dd.mm.yyyy or dd-mm-yyyy
    (r'\b(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})\b', "dmy"),
    # yyyy-mm-dd (ISO)
    (r'\b(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})\b', "ymd"),
    # Written dates: 11 April 2024, April 11, 2024
    (r'\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b', "dMy"),
    (r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b', "Mdy"),
    # mm/yyyy or mm.yyyy (partial) - only match if NOT preceded by digit+separator
    (r'(?<!\d[./\-]\d)(?<!\d[./\-])(\d{1,2})[./\-](\d{4})\b', "my"),
]

MONTH_MAP = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12"
}

# Document types that use specific date rules
LETTER_TYPES = [
    "site report", "assessment report", "building report", "roof report",
    "hail report", "progress report", "supplementary report",
    "supplementary technical assessment report", "notice of response",
    "idr fdl", "request for information", "written preliminary assessment",
    "initial claims advice", "weather pack"
]
SIGNED_TYPES = ["letter of engagement", "aaf to be signed"]
POLICY_TYPES = ["policy schedule", "certificate of insurance"]
PDS_TYPES = ["pds"]
LODGEMENT_TYPES = ["claim lodgement email", "claim lodgement form"]
QUOTE_TYPES = ["quote"]
PHOTO_TYPES = ["photo schedule"]


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


def extract_all_dates(text: str) -> list:
    """Extract all date candidates from text. Returns list of (date_str, is_partial, position)."""
    results = []
    for pattern, ptype in DATE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            date_str, is_partial = parse_date(text, ptype, match)
            if date_str:  # Skip invalid/empty dates
                results.append((date_str, is_partial, match.start()))
    return results


def find_page1_top_date(page1_text: str) -> Tuple[str, bool]:
    """Find the first date in the top portion of page 1."""
    # Consider the top ~40 lines or first 2000 chars
    top_text = page1_text[:2000]
    dates = extract_all_dates(top_text)
    if dates:
        return dates[0][0], dates[0][1]
    return "", False


def find_signed_date(text: str) -> str:
    """Look for a signature/execution date."""
    # Look for patterns like "Date signed:", "Signed:", "Executed:" near signature blocks
    patterns = [
        r'(?:date\s+signed|signed|executed|date\s+of\s+signing)\s*[:.]?\s*(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})',
        r'(?:date\s+signed|signed|executed|date\s+of\s+signing)\s*[:.]?\s*(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            # Re-extract the date from the match
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

    # 1. Formal letters and reports
    if any(t in doc_lower for t in LETTER_TYPES):
        date, is_partial = find_page1_top_date(page1_text)
        if date:
            return date, 18 if not is_partial else 12
        # fallback: any date in full text
        dates = extract_all_dates(full_text)
        if dates:
            return dates[0][0], 8
        return "NO DATE", 5

    # 2. Signed documents
    if any(t in doc_lower for t in SIGNED_TYPES):
        signed = find_signed_date(full_text)
        if signed:
            return signed, 18
        date, _ = find_page1_top_date(page1_text)
        if date:
            return date, 10
        return "NO DATE", 5

    # 3. Policy schedule / COI
    if any(t in doc_lower for t in POLICY_TYPES):
        inception = find_policy_inception_date(full_text)
        if inception:
            return inception, 18
        date, _ = find_page1_top_date(page1_text)
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

    # 8. Weather documents
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
