"""
AI-powered second-pass PII detection using Groq.
Identifies PII missed by the primary spaCy + regex pass.
"""
import json
import logging

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a privacy redaction assistant for Australian insurance documents. "
    "The text below has already had some PII removed (replaced with tokens like [CLIENT_ID_001]). "
    "Identify any remaining PII that was missed — policy numbers, claim numbers, ABN numbers, "
    "ACN numbers, phone numbers in unusual formats, email addresses, full property addresses. "
    'Return ONLY a JSON object with a single key "missed_pii" containing a list of the exact '
    'PII strings found. If nothing found return {"missed_pii": []}.'
)


class GroqRedactor:

    def redact_pass(self, lines: list) -> list:
        """Takes already-redacted lines. Returns list of additional PII strings found."""
        try:
            from src.services.ai_classifier import groq_classifier
            if not groq_classifier.is_available():
                return []
        except Exception:
            return []

        all_missed = []
        # Process in batches of 15 lines
        for i in range(0, len(lines), 15):
            batch = lines[i:i + 15]
            batch_text = "\n".join(batch)
            try:
                from groq import Groq
                from src.services.ai_classifier import _GROQ_API_KEY
                client = Groq(api_key=_GROQ_API_KEY)
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": batch_text}
                    ],
                    response_format={"type": "json_object"},
                    timeout=8,
                )
                result = json.loads(response.choices[0].message.content)
                missed = result.get("missed_pii", [])
                if isinstance(missed, list):
                    all_missed.extend(str(item) for item in missed if item)
            except Exception as e:
                logger.debug("Groq redaction pass error: %s", e)
                continue

        return all_missed


groq_redactor = GroqRedactor()
