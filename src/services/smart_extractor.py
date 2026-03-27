"""
Groq-assisted smart extraction for Verbatim Pack generation.
Extracts relevant verbatim passages from insurance claim documents
based on document type and VP section assignment.
"""
import json
import logging
import re
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# VP section definitions
# ---------------------------------------------------------------------------
VP_SECTIONS = {
    "VP1": "PDS QUOTABLE SECTIONS",
    "VP2": "COMPLAINANT EXPERT REPORTS",
    "VP3": "FF EXPERT REPORTS AND DECISIONS",
    "VP4": "SCOPES AND QUOTES",
    "VP5": "WEATHER EVIDENCE",
    "VP6": "SOLAR AND SPECIALIST REPORTS",
    "VP_OTHER": "OTHER DOCUMENTS",
}

# Document type -> VP section mapping
_TYPE_TO_VP = {
    "PDS": "VP1",
    "Product Disclosure Statement": "VP1",
    "Certificate of Insurance": "VP1",
    "Policy Schedule": "VP1",
    # VP2 - complainant expert (who != FF)
    "Roof Report": "VP2_OR_VP3",
    "Building Report": "VP2_OR_VP3",
    "Engineering Report": "VP2_OR_VP3",
    "Supplementary Report": "VP2_OR_VP3",
    "Progress Report": "VP2_OR_VP3",
    # VP3 - FF decisions
    "Desktop Assessment": "VP3",
    "Decline Letter": "VP3",
    "IDR FDL": "VP3",
    "Claims Team FDL": "VP3",
    "Re-inspection Report": "VP3",
    # VP4 - scopes and quotes
    "Scope of Repairs": "VP4",
    "Scope of Works": "VP4",
    "Quote": "VP4",
    "Variation Report": "VP4",
    # VP5 - weather
    "Hail Report": "VP5",
    "Weather Report": "VP5",
    "Weather Pack": "VP5",
    # VP6 - specialist
    "Solar Report": "VP6",
    "Solar PV Specialist Report": "VP6",
}

# Filename keyword -> document type fallback (when Groq unavailable)
_FILENAME_KEYWORDS = {
    "pds": "PDS",
    "product disclosure": "PDS",
    "report": "Building Report",
    "assessment": "Building Report",
    "engineering": "Engineering Report",
    "inspection": "Building Report",
    "supplementary": "Supplementary Report",
    "decision": "IDR FDL",
    "idr": "IDR FDL",
    "fdl": "IDR FDL",
    "decline": "Decline Letter",
    "response": "IDR FDL",
    "scope": "Scope of Works",
    "builder": "Scope of Works",
    "quote": "Quote",
    "works": "Scope of Works",
    "weather": "Weather Report",
    "bom": "Weather Report",
    "hail": "Hail Report",
    "solar": "Solar Report",
}


def _determine_vp_section(doc_type: str, who: str) -> str:
    """Map a document type + who to a VP section."""
    vp = _TYPE_TO_VP.get(doc_type, "VP_OTHER")
    if vp == "VP2_OR_VP3":
        return "VP3" if who == "FF" else "VP2"
    return vp


def _classify_by_filename(filename: str) -> tuple:
    """Fallback classification using filename keywords. Returns (what, who)."""
    fn_lower = filename.lower()
    for keyword, doc_type in _FILENAME_KEYWORDS.items():
        if keyword in fn_lower:
            who = "FF" if any(w in fn_lower for w in ["ff", "insurer", "sedgwick", "allianz"]) else "Complainant"
            return doc_type, who
    return "Unknown", "Unknown"


def _groq_call(system_prompt: str, user_prompt: str, timeout: int = 15) -> Optional[str]:
    """Make a Groq API call with retry on 429. Returns response text or None."""
    try:
        from src.services.ai_classifier import _GROQ_API_KEY, groq_classifier
        if not groq_classifier.is_available():
            return None
        from groq import Groq
        client = Groq(api_key=_GROQ_API_KEY)

        for attempt in range(2):
            try:
                response = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    timeout=timeout,
                )
                return response.choices[0].message.content
            except Exception as e:
                err_str = str(e)
                if "429" in err_str and attempt == 0:
                    logger.debug("Groq rate limited, retrying in 5s...")
                    time.sleep(5)
                    continue
                raise
    except Exception as e:
        logger.debug("Groq extraction call failed: %s", e)
        return None


def _parse_sections(raw_response: str) -> list:
    """Parse SECTION/PAGE/TEXT blocks from Groq response.
    Returns list of dicts: [{section, page, text}, ...]
    """
    if not raw_response:
        return []

    sections = []
    # Split on --- separators
    blocks = re.split(r'\n---\s*\n?', raw_response)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        section_match = re.search(r'SECTION:\s*(.+?)(?:\n|$)', block)
        page_match = re.search(r'PAGE:\s*(.+?)(?:\n|$)', block)
        text_match = re.search(r'TEXT:\s*(.*)', block, re.DOTALL)

        if section_match:
            section_name = section_match.group(1).strip()
            if "NOT FOUND" in section_name:
                continue
            page = page_match.group(1).strip() if page_match else "UNKNOWN"
            text = text_match.group(1).strip() if text_match else block
            sections.append({
                "section": section_name,
                "page": page,
                "text": text,
            })
        else:
            # Format not followed — include raw block with warning
            sections.append({
                "section": "[FORMAT WARNING] Raw extraction",
                "page": "UNKNOWN",
                "text": block,
            })

    return sections


# ---------------------------------------------------------------------------
# Extraction prompts
# ---------------------------------------------------------------------------

_PDS_SYSTEM = (
    "You are extracting verbatim text from an Australian insurance Product "
    "Disclosure Statement (PDS) for use in an AFCA complaint submission. "
    "Extract the COMPLETE text of each section exactly as written — do not "
    "paraphrase, summarise or clean up. Copy every word, punctuation mark "
    "and line break exactly."
)

_PDS_USER = """Extract these sections if present:
1. The insured events or general cover clause (usually headed 'What you are covered for', 'Insured events', or 'What we cover')
2. The Storm or Storm and hail specific cover clause
3. The 'How we settle' or 'How we pay' clause in full
4. Any definition of 'damage' if present
5. The wear and tear or gradual deterioration exclusion in full
6. The maintenance or 'your responsibility' exclusion in full
7. The 'How to establish your loss' or proof of loss clause

For each section found, output exactly this format:
SECTION: [printed heading exactly as it appears]
PAGE: [page number if visible, or UNKNOWN]
TEXT: [complete verbatim clause text including all sub-clauses]
---

If a section is not present write: SECTION: [name] NOT FOUND
---

Document text:
{text}"""

_EXPERT_SYSTEM = (
    "You are extracting verbatim text from an Australian insurance claim "
    "expert report for use in an AFCA complaint submission. Copy text "
    "exactly — no paraphrasing, no summarising, no cleaning up. Every word "
    "must match the source."
)

_EXPERT_USER = """Extract the COMPLETE text of these sections if present:
1. Conclusions section or equivalent (the expert's final opinion)
2. Scope of inspection or methodology section
3. Any passage quantifying damage (sheet counts, percentages, affected areas, structures inspected)
4. Any passage referencing NCC, BCA, QBCC, building standards, fixing offsets, batten requirements, or compliance methodology
5. Any causation opinion paragraph linking damage to a storm event
6. Any passage stating limitations of the inspection or testing methodology (especially for FF expert reports)
7. Any recommendation for further specialist assessment

For each section output:
SECTION: [section heading or description]
PAGE: [page number if visible, or UNKNOWN]
TEXT: [complete verbatim text]
---

This is a {report_type} report. Pay special attention to:
{focus_area}

Document text:
{text}"""

_FF_DECISION_SYSTEM = (
    "You are extracting verbatim text from an Australian insurance company "
    "decision letter or IDR response for use in an AFCA complaint submission. "
    "Copy text exactly — no paraphrasing."
)

_FF_DECISION_USER = """Extract the COMPLETE text of these sections if present:
1. The stated reason for denial or partial acceptance
2. Any policy exclusion cited — include the exact clause heading and full exclusion text as quoted in the letter
3. Any statement about what the insurer will or will not fund
4. Any cash offer amount and how it was calculated
5. Any reference to the insurer's builder or scope of works
6. Any statement about TB32, percentage of damage, or thresholds
7. Any statement directing the complainant to AFCA

For each section output:
SECTION: [description]
PAGE: [page number if visible, or UNKNOWN]
TEXT: [complete verbatim text]
---

Document text:
{text}"""

_SCOPE_SYSTEM = (
    "You are extracting verbatim text from an Australian insurance claim "
    "scope of works or builder quote for use in an AFCA complaint submission. "
    "Copy text exactly."
)

_SCOPE_USER = """Extract the COMPLETE text of these sections if present:
1. Any compliance or methodology note explaining why certain works are required (fixing offsets, batten replacement, elevation-based replacement, partial replacement constraints)
2. Any QBCC, NCC, or building standard reference
3. Any passage explaining why partial or sheet-by-sheet replacement is not compliant
4. The scope total cost figure and key line items
5. Any 'Notification of QBCC Requirements' section
6. Any certification or building approval note

For each section output:
SECTION: [description]
PAGE: [page number if visible, or UNKNOWN]
TEXT: [complete verbatim text]
---

Document text:
{text}"""

_WEATHER_SYSTEM = (
    "You are extracting verbatim text from a weather evidence document "
    "for use in an AFCA complaint submission. Copy exactly."
)

_WEATHER_USER = """Extract the COMPLETE text of these passages if present:
1. The property address or coordinates identification passage
2. The hail event data rows for the relevant date (date, hail size, distance from risk address)
3. Any storm warning text reproduced in the document
4. Any passage stating the methodology or data source

For each passage output:
SECTION: [description]
PAGE: [page number or UNKNOWN]
TEXT: [complete verbatim text]
---

Document text:
{text}"""

_SOLAR_SYSTEM = (
    "You are extracting verbatim text from a solar or specialist technical "
    "report for use in an AFCA complaint submission. Copy exactly — no "
    "paraphrasing."
)

_SOLAR_USER = """Extract the COMPLETE text of these sections if present:
1. The conclusions section stating what testing found
2. Any passage stating the testing method used (EL testing, thermal imaging, visual inspection)
3. Any passage on non-reusable components or compliance requirements for reinstatement
4. Any passage on whether event-related damage was found (note: internal inconsistencies between sections matter)

For each section output:
SECTION: [description]
PAGE: [page number or UNKNOWN]
TEXT: [complete verbatim text]
---

Document text:
{text}"""


# ---------------------------------------------------------------------------
# SmartExtractor class
# ---------------------------------------------------------------------------

class SmartExtractor:
    """Processes a single document and returns structured extraction results."""

    def classify_document(self, text: str, filename: str) -> tuple:
        """Classify a document. Returns (what, who, used_groq)."""
        try:
            from src.services.ai_classifier import groq_classifier
            if groq_classifier.is_available():
                result = groq_classifier.classify_document(text)
                if result and result.get("what"):
                    return result["what"], result.get("who", "Unknown"), True
        except Exception as e:
            logger.debug("Classification fallback: %s", e)

        what, who = _classify_by_filename(filename)
        return what, who, False

    def extract_pds(self, text: str, filename: str) -> list:
        prompt = _PDS_USER.format(text=text[:6000])
        raw = _groq_call(_PDS_SYSTEM, prompt, timeout=15)
        if raw:
            return _parse_sections(raw)
        return []

    def extract_expert_report(self, text: str, filename: str, report_type: str) -> list:
        if report_type == "ff_expert":
            focus = "methodology limitations and concessions"
        else:
            focus = "causation conclusions and compliance methodology"
        prompt = _EXPERT_USER.format(
            text=text[:6000], report_type=report_type, focus_area=focus
        )
        raw = _groq_call(_EXPERT_SYSTEM, prompt, timeout=15)
        if raw:
            return _parse_sections(raw)
        return []

    def extract_ff_decision(self, text: str, filename: str) -> list:
        prompt = _FF_DECISION_USER.format(text=text[:4000])
        raw = _groq_call(_FF_DECISION_SYSTEM, prompt, timeout=15)
        if raw:
            return _parse_sections(raw)
        return []

    def extract_scope(self, text: str, filename: str, scope_type: str) -> list:
        prompt = _SCOPE_USER.format(text=text[:5000])
        raw = _groq_call(_SCOPE_SYSTEM, prompt, timeout=15)
        if raw:
            return _parse_sections(raw)
        return []

    def extract_weather(self, text: str, filename: str) -> list:
        prompt = _WEATHER_USER.format(text=text[:3000])
        raw = _groq_call(_WEATHER_SYSTEM, prompt, timeout=15)
        if raw:
            return _parse_sections(raw)
        return []

    def extract_solar_specialist(self, text: str, filename: str) -> list:
        prompt = _SOLAR_USER.format(text=text[:4000])
        raw = _groq_call(_SOLAR_SYSTEM, prompt, timeout=15)
        if raw:
            return _parse_sections(raw)
        return []

    def process_document(self, text: str, filename: str) -> dict:
        """Process a single document. Returns structured result dict.

        Returns:
            {
                "filename": str,
                "doc_type": str,
                "who": str,
                "vp_section": str,
                "used_groq": bool,
                "passages": [{"section": str, "page": str, "text": str}, ...],
                "fallback": bool,  # True if raw text was used
            }
        """
        doc_type, who, used_groq_classify = self.classify_document(text, filename)
        vp_section = _determine_vp_section(doc_type, who)

        result = {
            "filename": filename,
            "doc_type": doc_type,
            "who": who,
            "vp_section": vp_section,
            "used_groq": False,
            "passages": [],
            "fallback": False,
        }

        try:
            passages = self._extract_by_type(text, filename, doc_type, who)
            if passages:
                result["passages"] = passages
                result["used_groq"] = True
            else:
                # Groq returned nothing — use raw text
                result["passages"] = [{
                    "section": doc_type or "Document",
                    "page": "UNKNOWN",
                    "text": text[:2000],
                }]
                result["fallback"] = True
        except Exception as e:
            logger.debug("Extraction failed for %s: %s", filename, e)
            result["passages"] = [{
                "section": "[GROQ EXTRACTION FAILED — raw text follows — verify manually]",
                "page": "UNKNOWN",
                "text": text[:2000],
            }]
            result["fallback"] = True

        return result

    def _extract_by_type(self, text: str, filename: str, doc_type: str, who: str) -> list:
        """Dispatch to the correct extraction method based on document type."""
        dt_lower = doc_type.lower() if doc_type else ""

        if "pds" in dt_lower or "product disclosure" in dt_lower:
            return self.extract_pds(text, filename)

        if any(t in dt_lower for t in ["roof report", "building report",
                                         "engineering report", "supplementary report",
                                         "progress report"]):
            report_type = "ff_expert" if who == "FF" else "complainant_expert"
            return self.extract_expert_report(text, filename, report_type)

        if any(t in dt_lower for t in ["desktop", "decline", "idr", "fdl",
                                         "re-inspection", "claims team"]):
            return self.extract_ff_decision(text, filename)

        if any(t in dt_lower for t in ["scope", "quote", "variation"]):
            scope_type = "ff_scope" if who == "FF" else "complainant_scope"
            return self.extract_scope(text, filename, scope_type)

        if any(t in dt_lower for t in ["weather", "hail", "bom"]):
            return self.extract_weather(text, filename)

        if any(t in dt_lower for t in ["solar", "specialist"]):
            return self.extract_solar_specialist(text, filename)

        # No specific extraction method — return empty (caller uses raw text)
        return []


smart_extractor = SmartExtractor()
