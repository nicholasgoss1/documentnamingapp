"""
Normalisation engine for filenames and components.
"""
import re
from typing import Optional

from src.core.settings import Settings
from src.services.date_engine import normalize_date


def normalize_entity(entity: str, settings: Settings) -> str:
    """Normalize entity to preferred label using alias mapping."""
    if not entity:
        return ""
    aliases = settings.get("entity_aliases", {})
    # Check exact alias match
    for alias, canonical in aliases.items():
        if entity.lower() == alias.lower():
            return canonical
    # Check preferred entities for case normalization
    preferred = settings.get("preferred_entities", [])
    for pref in preferred:
        if entity.lower() == pref.lower():
            return pref
    return entity


def normalize_what(what: str, settings: Settings) -> str:
    """Normalize the WHAT field using preferred labels."""
    if not what:
        return ""
    preferred = settings.get("preferred_doc_labels", [])
    what_lower = what.lower().strip()
    for label in preferred:
        if label.lower() == what_lower:
            return label
    # Title case fallback
    return smart_title_case(what)


def smart_title_case(text: str) -> str:
    """Title case preserving acronyms and special tokens."""
    acronyms = {"afca", "qbe", "pds", "idr", "fdl", "coi", "acb", "ruca", "aaf", "bom", "nor"}
    words = text.split()
    result = []
    for word in words:
        if word.lower() in acronyms:
            result.append(word.upper())
        elif word.startswith("$"):
            result.append(word)
        elif word.lower() in ("from", "to", "of", "the", "and", "for", "in", "on", "at", "by"):
            result.append(word.lower())
        else:
            result.append(word.capitalize())
    # Always capitalize first word
    if result:
        result[0] = result[0].capitalize() if result[0][0].islower() else result[0]
    return " ".join(result)


def normalize_who(who: str) -> str:
    """Normalize WHO field."""
    mapping = {
        "ff": "FF",
        "complainant": "Complainant",
        "afca": "AFCA",
        "unknown": "UNKNOWN",
    }
    return mapping.get(who.lower().strip(), who)


def normalize_full_filename(who: str, date: str, entity: str, what: str,
                            is_unsure: bool, settings: Settings) -> str:
    """Build and normalize a complete filename."""
    who = normalize_who(who)
    date = normalize_date(date)
    entity = normalize_entity(entity, settings)
    what = normalize_what(what, settings)

    parts = []
    if who:
        parts.append(who)
    if date:
        parts.append(date)
    if entity:
        parts.append(entity)
    if what:
        parts.append(what)
    if is_unsure:
        parts.append("UNSURE")

    name = " - ".join(parts)
    name = clean_filename(name)
    return name + ".pdf"


def clean_filename(name: str) -> str:
    """Clean a filename string for Windows compatibility."""
    # Remove invalid characters
    invalid_chars = '<>:"/\\|?*'
    for ch in invalid_chars:
        name = name.replace(ch, "")
    # Strip duplicate spaces
    name = re.sub(r' {2,}', ' ', name)
    # Strip repeated separators like " - - " or "- -"
    name = re.sub(r'(\s*-\s*){2,}', ' - ', name)
    # Strip leading/trailing whitespace and separators
    name = name.strip(' -.')
    # Remove .pdf if accidentally included (caller adds it)
    if name.lower().endswith('.pdf'):
        name = name[:-4].strip(' -.')
    return name


def fix_not_date(text: str) -> str:
    """Fix common typo NOT DATE -> NO DATE."""
    return re.sub(r'\bNOT\s+DATE\b', 'NO DATE', text, flags=re.IGNORECASE)


def normalize_date_in_string(text: str) -> str:
    """Fix date formatting issues like 08.1.2025 -> 08.01.2025."""
    def fix_date(m):
        d, m_str, y = m.group(1), m.group(2), m.group(3)
        return f"{int(d):02d}.{int(m_str):02d}.{y}"
    return re.sub(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', fix_date, text)
