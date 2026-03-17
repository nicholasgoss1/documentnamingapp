"""
Document classifier: infers WHO, ENTITY, WHAT from extracted text and filename.
All processing is local.
"""
import re
from typing import Tuple, Optional

from src.core.settings import Settings


def detect_annexure(filename: str) -> Tuple[bool, str]:
    """Detect if filename is an annexure wrapper. Returns (is_annexure, annexure_number)."""
    m = re.match(r'^[Aa]nnexure\s*(\d+)', filename)
    if m:
        return True, m.group(1)
    m = re.match(r'^[Aa]nnex\.?\s*(\d+)', filename)
    if m:
        return True, m.group(1)
    return False, ""


def infer_who(page1_text: str, full_text: str, filename: str,
              entity: str, settings: Settings,
              page1_regions: dict = None) -> Tuple[str, int]:
    """
    Infer the WHO field based on provenance rules.
    Uses spatial layout when available: entities/keywords in the "from"
    regions (top-right letterhead + bottom signature) indicate the author,
    while the top-left region is the addressee.
    Returns (who_string, confidence_contribution 0-20).
    """
    text_lower = (page1_text + " " + full_text + " " + filename).lower()
    # Normalize whitespace for phrase matching — PDF line breaks split phrases
    text_normalized = re.sub(r'\s+', ' ', text_lower)
    entity_lower = entity.lower() if entity else ""
    mapping = settings.get("who_mapping", {})

    complainant_entities = [e.lower() for e in mapping.get("complainant_entities", [])]
    ff_entities = [e.lower() for e in mapping.get("ff_entities", [])]
    afca_entities = [e.lower() for e in mapping.get("afca_entities", [])]

    # --- Spatial layout: check the "from" region (top-right only) ---
    # In letter layout, the top-right contains the letterhead/logo which
    # identifies who WROTE the document.  We intentionally exclude the
    # bottom region because body text often bleeds into it (e.g. a
    # ClaimsCo letter discussing Allianz's decision would have "Allianz"
    # in the lower body, falsely triggering an FF match).
    if page1_regions:
        from_text = page1_regions.get("top_right", "").lower()
        if from_text.strip():
            for ent in complainant_entities:
                if ent in from_text:
                    return "Complainant", 19
            for ent in afca_entities:
                if ent in from_text:
                    return "AFCA", 19
            for ent in ff_entities:
                if ent in from_text:
                    return "FF", 19

    # Check entity first (most reliable after spatial)
    if entity_lower:
        if entity_lower in complainant_entities:
            return "Complainant", 18
        if entity_lower in afca_entities:
            return "AFCA", 18
        if entity_lower in ff_entities:
            return "FF", 18

    # Check keywords in text
    afca_kw = mapping.get("afca_keywords", [])
    complainant_kw = mapping.get("complainant_keywords", [])
    ff_kw = mapping.get("ff_keywords", [])

    afca_score = sum(1 for kw in afca_kw if kw.lower() in text_lower)
    comp_score = sum(1 for kw in complainant_kw if kw.lower() in text_lower)
    ff_score = sum(1 for kw in ff_kw if kw.lower() in text_lower)

    # ClaimsCo documents are always Complainant-side
    # Check both the name and distinctive authorship phrases (logo may be an image)
    if "claimsco" in text_lower or "on behalf of our mutual client" in text_normalized:
        return "Complainant", 17

    # Complainant-side document types (check before AFCA)
    comp_doc_types = [
        "afca submission", "submission to afca", "letter of engagement",
        "authority and access form", "aaf",
        "on behalf of the complainant", "authorised representative",
    ]
    for dt in comp_doc_types:
        if dt in text_lower:
            return "Complainant", 16

    # AFCA-issued documents (from AFCA to parties)
    if "afca" in text_lower and ("request for information" in text_lower
                                   or "preliminary assessment" in text_lower):
        return "AFCA", 16
    # AFCA notices - only if not from complainant side
    if "australian financial complaints authority" in text_lower:
        if "request for information" in text_lower or "preliminary assessment" in text_lower:
            return "AFCA", 16

    # Specific entity checks
    for ent in complainant_entities:
        if ent in text_lower:
            return "Complainant", 15

    # Complainant notice of response (responds to insurer)
    if "notice of response" in text_lower:
        if any(kw in text_lower for kw in ["claimsco", "complainant", "on behalf", "we respond"]):
            return "Complainant", 14

    if afca_score > ff_score and afca_score > comp_score:
        return "AFCA", 12
    if comp_score > ff_score:
        return "Complainant", 12
    if ff_score > 0:
        return "FF", 12

    # Default to FF for most insurer-side / third-party material
    return "FF", 6


def _find_entities_in_text(text: str, sorted_keys: list, search_map: dict) -> list:
    """Find all known entities in a text string. Returns list of (canonical_name, position)."""
    text_lower = text.lower()
    found = []
    for key in sorted_keys:
        if key in text_lower:
            canonical = search_map[key]
            if canonical not in [f[0] for f in found]:
                pos = text_lower.index(key)
                found.append((canonical, pos))
    return found


def infer_entity(page1_text: str, full_text: str, filename: str,
                 settings: Settings, page1_regions: dict = None) -> Tuple[str, int]:
    """
    Infer the ENTITY field by looking for known entities.
    Uses spatial layout when available: top-right region (letterhead/logo)
    is the strongest signal for document authorship, followed by the
    full header area.  The top-left region (addressee) is deprioritised.
    Returns (entity_string, confidence_contribution 0-20).
    """
    preferred = settings.get("preferred_entities", [])
    aliases = settings.get("entity_aliases", {})

    # Build a search map: all preferred entities + their aliases
    search_map = {}
    for ent in preferred:
        search_map[ent.lower()] = ent
    for alias, canonical in aliases.items():
        search_map[alias.lower()] = canonical

    sorted_keys = sorted(search_map.keys(), key=len, reverse=True)

    # Phase 0: spatial layout — top-right region (letterhead / "from" party)
    if page1_regions:
        top_right = page1_regions.get("top_right", "")
        if top_right:
            found = _find_entities_in_text(top_right, sorted_keys, search_map)
            if found:
                found.sort(key=lambda x: x[1])
                return found[0][0], 20

    # Phase 0.5: signature / sign-off area — strong authorship signal.
    # Check the bottom region of page 1 and the last portion of the full
    # document text (signature block on the final page).
    sig_texts = []
    if page1_regions:
        bottom = page1_regions.get("bottom", "")
        if bottom:
            sig_texts.append(bottom)
    if full_text:
        sig_texts.append(full_text[-800:])
    for sig_text in sig_texts:
        sig_found = _find_entities_in_text(sig_text, sorted_keys, search_map)
        if sig_found:
            # Prefer complainant-side entities in signature (the author)
            complainant_ents = set(
                e.lower() for e in settings.get("who_mapping", {}).get(
                    "complainant_entities", []))
            for entity, pos in sig_found:
                if entity.lower() in complainant_ents:
                    return entity, 20
            # Otherwise use the first entity found in the signature
            sig_found.sort(key=lambda x: x[1])
            return sig_found[0][0], 18

    # Phase 1: search the header / letterhead area of page 1 only
    header_text = (page1_text[:600] if page1_text else "").lower()
    header_found = _find_entities_in_text(header_text, sorted_keys, search_map)

    if header_found:
        header_found.sort(key=lambda x: x[1])
        return header_found[0][0], 20

    # Phase 2: search the full page 1 text
    page1_lower = (page1_text or "").lower()
    page1_found = _find_entities_in_text(page1_lower, sorted_keys, search_map)

    if page1_found:
        page1_found.sort(key=lambda x: x[1])
        return page1_found[0][0], 15

    # Phase 3: fall back to full text + filename
    text = (full_text + " " + filename).lower()
    fallback_found = _find_entities_in_text(text, sorted_keys, search_map)

    if fallback_found:
        fallback_found.sort(key=lambda x: x[1])
        return fallback_found[0][0], 10

    return "", 0


def infer_what(page1_text: str, full_text: str, filename: str,
               settings: Settings) -> Tuple[str, int]:
    """
    Infer the WHAT (document type/description) field.
    Returns (what_string, confidence_contribution 0-20).
    """
    doc_keywords = settings.get("doc_type_keywords", {})
    preferred_labels = settings.get("preferred_doc_labels", [])
    text_lower = (page1_text + " " + filename).lower()
    filename_lower = filename.lower()
    full_lower = full_text.lower()

    best_match = ""
    best_score = 0
    best_specificity = 0  # Length of matching keyword (prefer longer/more specific)

    for label, keywords in doc_keywords.items():
        for kw in keywords:
            kw_lower = kw.lower()
            # Filename match is strongest signal (human-assigned name)
            if kw_lower in filename_lower:
                score = 30
            elif kw_lower in text_lower:
                score = 20
                if kw_lower in page1_text[:500].lower():
                    score = 25  # Very high if in heading area
            elif kw_lower in full_lower:
                score = 10
            else:
                continue

            specificity = len(kw_lower)
            # Prefer more specific (longer) keyword matches at equal or better score
            if score > best_score or (score == best_score and specificity > best_specificity):
                best_score = score
                best_match = label
                best_specificity = specificity

    if best_match:
        # Handle progress report numbering
        if best_match == "Progress Report":
            # Try to find a number
            m = re.search(r'progress\s+report\s*[#:]?\s*(\d+)', text_lower)
            if m:
                best_match = f"Progress Report {m.group(1)}"
            else:
                best_match = "Progress Report 1"

        # Check for Notice of Response from QBE specifically
        if best_match == "Notice of Response":
            if "qbe" in text_lower:
                best_match = "Notice of Response from QBE"

        return best_match, min(20, best_score)

    # Fallback: try to extract a title from page 1 heading
    heading = extract_heading(page1_text)
    if heading:
        return normalize_what_label(heading, preferred_labels), 8

    # Last resort: use original filename cleaned up
    clean = clean_filename_for_what(filename)
    if clean:
        return normalize_what_label(clean, preferred_labels), 4

    return "", 0


def extract_heading(page1_text: str) -> str:
    """Try to extract a document title/heading from the top of page 1."""
    lines = page1_text.strip().split("\n")
    # Look for a prominent line in the first 10 lines
    for line in lines[:10]:
        line = line.strip()
        if not line:
            continue
        # Skip very short lines (likely page numbers, logos)
        if len(line) < 5:
            continue
        # Skip lines that look like addresses or dates
        if re.match(r'^\d', line) and len(line) < 20:
            continue
        if "@" in line or "www." in line or "http" in line:
            continue
        # This might be a heading
        if len(line) < 80:
            return line
    return ""


def clean_filename_for_what(filename: str) -> str:
    """Clean original filename to extract a potential WHAT value."""
    name = filename
    # Strip common file extensions (the file may be a converted image)
    for ext in [".pdf", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".bmp"]:
        if name.lower().endswith(ext):
            name = name[:-len(ext)]
            break
    # Remove common prefixes
    name = re.sub(r'^[Aa]nnexure\s*\d+\s*[-_]?\s*', '', name)
    # Remove dates
    name = re.sub(r'\d{1,2}[./\-]\d{1,2}[./\-]\d{4}', '', name)
    name = re.sub(r'\d{4}[./\-]\d{1,2}[./\-]\d{1,2}', '', name)
    # Clean separators
    name = re.sub(r'[_\-]+', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    # Reject meaningless names (generic scan/image filenames)
    meaningless = {"image", "scan", "photo", "img", "doc", "document",
                   "file", "page", "untitled", "screenshot"}
    if re.sub(r'\d+', '', name).strip().lower() in meaningless:
        return ""
    return name


def normalize_what_label(label: str, preferred_labels: list) -> str:
    """Normalize a WHAT label to title case and match preferred labels."""
    label_lower = label.lower().strip()
    for preferred in preferred_labels:
        if preferred.lower() == label_lower:
            return preferred
        if label_lower in preferred.lower() or preferred.lower() in label_lower:
            return preferred
    # Title case
    return title_case_smart(label)


def title_case_smart(text: str) -> str:
    """Title case but preserve known acronyms."""
    acronyms = {"afca", "qbe", "pds", "idr", "fdl", "coi", "acb", "ruca", "aaf", "bom"}
    words = text.split()
    result = []
    for word in words:
        if word.lower() in acronyms:
            result.append(word.upper())
        elif word.startswith("$"):
            result.append(word)
        else:
            result.append(word.capitalize())
    return " ".join(result)


def should_include_entity(doc_type: str, entity: str, settings: Settings) -> bool:
    """Determine if ENTITY should be included based on document class rules."""
    if not entity:
        return False
    rules = settings.get("entity_include_rules", {})
    # Check exact match
    if doc_type in rules:
        return rules[doc_type]
    # Check partial match
    for rule_type, include in rules.items():
        if rule_type.lower() in doc_type.lower():
            return include
    # Default: include if entity is present
    return True


def extract_quote_amount(text: str) -> str:
    """Try to extract a dollar amount from a quote document."""
    patterns = [
        r'\$\s*([\d,]+\.?\d*)',
        r'total[:\s]*\$\s*([\d,]+\.?\d*)',
        r'quote[:\s]*\$\s*([\d,]+\.?\d*)',
        r'amount[:\s]*\$\s*([\d,]+\.?\d*)',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            amount = m.group(1)
            # Format with $ prefix
            return f"${amount}"
    return ""
