import json
import logging

logger = logging.getLogger(__name__)

_GROQ_API_KEY = "gsk_PASTE_YOUR_KEY_HERE"

_SYSTEM_PROMPT = (
    "You are a document classifier for Australian insurance claim files. "
    "Read the extracted PDF text and identify who issued it, the entity name, "
    "the primary date, and the document type. "
    "Always respond with valid JSON only. No explanation. No markdown. No commentary."
)

_USER_PROMPT_TEMPLATE = '''Classify this insurance document.

Return ONLY a JSON object with exactly these fields:
- who: one of exactly: Complainant, FF, AFCA, Unknown
- entity: the company or firm name (e.g. AusCoast Builders, Sedgwick, RACQ, Kehoe Myers) or empty string if none
- date: the primary document date in DD.MM.YYYY format, or NO DATE if no date found
- what: the document type, choose the best match from: Roof Report, IDR FDL, Quote, Scope of Repairs, Building Report, Supplementary Report, Letter of Engagement, Certificate of Insurance, PDS, AFCA Submission, Notice of Response, Photo Schedule, Solar Report, Engineering Report, Scope of Works, Invoice, Agent Authority Form, Decline Letter, Desktop Assessment, Re-inspection Report, Policy Schedule, Claim Lodgement Email, Written Preliminary Assessment, Request for Information, Progress Report, Hail Report, Weather Report

Document text:
{text}'''


class GroqClassifier:

    def is_available(self) -> bool:
        return bool(_GROQ_API_KEY) and _GROQ_API_KEY != "gsk_PASTE_YOUR_KEY_HERE"

    def classify_document(self, text: str) -> dict | None:
        if not self.is_available():
            return None
        try:
            from groq import Groq
            client = Groq(api_key=_GROQ_API_KEY)
            user_prompt = _USER_PROMPT_TEMPLATE.format(text=text[:1200])
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
