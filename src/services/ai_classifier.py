import json
import logging
import os

logger = logging.getLogger(__name__)

# Load API key from environment variable, or from a local .env-style key file.
# To configure: set GROQ_API_KEY environment variable, or create
# src/services/.groq_key containing just the key string.
_GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
if not _GROQ_API_KEY:
    _key_file = os.path.join(os.path.dirname(__file__), ".groq_key")
    if os.path.exists(_key_file):
        try:
            with open(_key_file, "r") as f:
                _GROQ_API_KEY = f.read().strip()
        except Exception:
            pass

_SYSTEM_PROMPT = (
    "You are a document classifier for Australian insurance claim files. "
    "Read the extracted PDF text and identify who issued it, the entity name, "
    "the primary date, and the document type. "
    "Always respond with valid JSON only. No explanation. No markdown. No commentary."
)

_USER_PROMPT_TEMPLATE = '''Classify this insurance document for an Australian insurance claims management company.

The filename is: {filename}

IMPORTANT — Read the filename carefully. Australian claim files follow this naming pattern:
  [WHO] - [DATE] - [ENTITY] - [WHAT]
The ENTITY is usually the third part of the filename separated by ' - '. Extract it directly from the filename if visible.

Common entities you may see:
  Insurers: Allianz, Suncorp, RACQ, QBE, NRMA, AAMI, GIO, Budget Direct, Youi, Vero, Zurich, IAG, Chubb
  Builders/Engineers: AusCoast Builders, BMG Engineering, Sedgwick, Ezy Projects, Campbell Constructions, Ambrose Construct Group, Kehoe Myers, Salt Water Roofing, Aizer Insurance Builders, InTouch Projects, Live Electrical
  Solar/Specialist: PV Lab Australia, Solarez, Solarez Energy
  Weather: WeatherWatch, Early Warning Network
  ClaimsCo: ClaimsCo (this is the claims management firm, not the insurer — if ClaimsCo is the entity, WHO is Complainant)

Return ONLY a JSON object with exactly these fields:
- who: one of exactly: Complainant, FF, AFCA, Unknown (FF means Financial Firm i.e. the insurer)
- entity: the company or firm name — extract from filename first, then confirm from document text. Never leave blank if visible in filename. Return the clean company name only (e.g. 'Allianz' not 'Allianz Australia Insurance Ltd')
- date: the primary document date in DD.MM.YYYY format, or NO DATE if no date found
- what: the document type, best match from: Roof Report, IDR FDL, Quote, Scope of Repairs, Building Report, Supplementary Report, Letter of Engagement, Certificate of Insurance, PDS, AFCA Submission, Notice of Response, Photo Schedule, Solar Report, Solar Testing Report, Engineering Report, Scope of Works, Invoice, Agent Authority Form, Decline Letter, Desktop Assessment, Re-inspection Report, Policy Schedule, Claim Lodgement Email, Written Preliminary Assessment, Request for Information, Progress Report, Hail Report, Weather Report, Variation Report, Delegation of Authority

Filename: {filename}
Document text (first 1200 chars):
{text}'''


class GroqClassifier:

    def is_available(self) -> bool:
        return bool(_GROQ_API_KEY) and _GROQ_API_KEY.startswith("gsk_")

    def classify_document(self, text: str, filename: str = "") -> dict | None:
        if not self.is_available():
            return None
        try:
            from groq import Groq
            client = Groq(api_key=_GROQ_API_KEY)
            user_prompt = _USER_PROMPT_TEMPLATE.format(
                text=text[:1200], filename=filename
            )
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                timeout=8,
            )
            result = json.loads(response.choices[0].message.content)
            # Validate required keys
            for key in ("who", "entity", "date", "what"):
                if key not in result:
                    logger.debug("Groq response missing key: %s", key)
                    return None
            return result
        except Exception as e:
            logger.debug("Groq classification error: %s", e)
            return None


groq_classifier = GroqClassifier()
