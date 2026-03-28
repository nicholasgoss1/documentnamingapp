"""
Groq AI document classifier with few-shot learning from corrections.
"""
import json
import logging
import os

logger = logging.getLogger(__name__)

# Load API key from environment variable, or from local key files.
_GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
if not _GROQ_API_KEY:
    for _kf in [
        os.path.join(os.path.dirname(__file__), ".groq_key"),
        "C:/Projects/Groq API key.txt",
    ]:
        if os.path.exists(_kf):
            try:
                with open(_kf, "r") as f:
                    _GROQ_API_KEY = f.read().strip()
                if _GROQ_API_KEY:
                    break
            except Exception:
                pass

_SYSTEM_PROMPT = (
    "You are a document classifier for Australian insurance claim files. "
    "Read the extracted PDF text and identify who issued it, the entity name, "
    "the primary date, and the document type. "
    "Always respond with valid JSON only. No explanation. No markdown. No commentary."
)

_USER_PROMPT_TEMPLATE = '''Classify this insurance claim document for an Australian insurance claims management company.

FILENAME: {filename}

The filename follows this pattern: [WHO] - [DATE] - [ENTITY] - [WHAT]
Extract the ENTITY directly from the third segment of the filename where possible.

Common entities:
  Insurers (WHO = FF): Allianz, Suncorp, RACQ, QBE, NRMA, AAMI, GIO, Budget Direct, Youi, Vero, Zurich, IAG, Chubb
  Builders/Engineers (WHO = Complainant or FF): AusCoast Builders, BMG Engineering, Sedgwick, Ezy Projects, Campbell Constructions, Ambrose Construct Group, Kehoe Myers, Salt Water Roofing, Aizer Insurance Builders, InTouch Projects, Live Electrical
  Solar/Specialist: PV Lab Australia, Solarez, Solarez Energy
  Weather: WeatherWatch, Early Warning Network
  ClaimsCo = the claims management firm, WHO = Complainant

{few_shot_examples}

Return ONLY a JSON object with exactly these fields:
- who: one of: Complainant, FF, AFCA, Unknown
- entity: company name from filename third segment first, then confirmed from text. Never leave blank if visible in filename. Return clean name only (e.g. 'Allianz' not 'Allianz Australia Insurance Ltd')
- date: DD.MM.YYYY or NO DATE
- what: best match from: Roof Report, IDR FDL, Quote, Scope of Repairs, Building Report, Supplementary Report, Letter of Engagement, Certificate of Insurance, PDS, AFCA Submission, Notice of Response, Photo Schedule, Solar Report, Solar Testing Report, Engineering Report, Scope of Works, Invoice, Agent Authority Form, Decline Letter, Desktop Assessment, Re-inspection Report, Policy Schedule, Claim Lodgement Email, Written Preliminary Assessment, Request for Information, Progress Report, Hail Report, Weather Report, Variation Report, Delegation of Authority

DOCUMENT TEXT (first 1200 chars):
{text}'''


def _build_few_shot_block() -> str:
    """Build few-shot examples string from corrections or seed examples."""
    examples = []
    try:
        from src.services.corrections_store import get_few_shot_examples
        examples = get_few_shot_examples(5)
    except Exception:
        pass

    if len(examples) < 5:
        try:
            from src.services.seed_examples import SEED_EXAMPLES
            # Also try learned examples
            learned = _load_learned_examples()
            all_seeds = list(SEED_EXAMPLES) + learned
            seen = {ex["filename"] for ex in examples}
            for seed in all_seeds:
                if seed["filename"] not in seen:
                    examples.append(seed)
                    seen.add(seed["filename"])
                if len(examples) >= 5:
                    break
        except Exception:
            pass

    if not examples:
        return ""

    lines = ["Here are examples of correct classifications:"]
    for ex in examples[:5]:
        fn = ex.get("filename", "")
        r = ex.get("result", {})
        lines.append(
            f'  "{fn}" -> {{"who": "{r.get("who", "")}", '
            f'"entity": "{r.get("entity", "")}", '
            f'"date": "{r.get("date", "")}", '
            f'"what": "{r.get("what", "")}"}}'
        )
    return "\n".join(lines)


def _load_learned_examples() -> list:
    """Load learned examples from %LOCALAPPDATA% if they exist."""
    try:
        if os.name == "nt":
            base = os.environ.get("LOCALAPPDATA", "")
        else:
            base = os.path.expanduser("~/.local/share")
        path = os.path.join(base, "ClaimFileRenamer", "learned_examples.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []


class GroqClassifier:

    def is_available(self) -> bool:
        return bool(_GROQ_API_KEY) and _GROQ_API_KEY.startswith("gsk_")

    def classify_document(self, text: str, filename: str = "") -> dict | None:
        if not self.is_available():
            return None

        # Check corrections cache for exact filename match
        try:
            from src.services.corrections_store import lookup_by_filename
            cached = lookup_by_filename(filename)
            if cached:
                logger.debug("Corrections cache hit for: %s", filename)
                return cached
        except Exception:
            pass

        try:
            from groq import Groq
            client = Groq(api_key=_GROQ_API_KEY)
            few_shot = _build_few_shot_block()
            user_prompt = _USER_PROMPT_TEMPLATE.format(
                text=text[:1200], filename=filename, few_shot_examples=few_shot
            )
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                timeout=8,
            )
            result = json.loads(response.choices[0].message.content)
            for key in ("who", "entity", "date", "what"):
                if key not in result:
                    logger.debug("Groq response missing key: %s", key)
                    return None

            # Pre-populate entity from corrections if Groq left it blank
            if not result.get("entity") and filename:
                try:
                    from src.services.classifier import _extract_entity_from_filename
                    from src.core.settings import Settings
                    s = Settings()
                    fn_entity, _ = _extract_entity_from_filename(filename, s)
                    if fn_entity:
                        result["entity"] = fn_entity
                except Exception:
                    pass

            return result
        except Exception as e:
            logger.debug("Groq classification error: %s", e)
            return None


groq_classifier = GroqClassifier()
