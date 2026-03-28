"""
Redaction corrections store — logs when users add or remove AI redaction boxes.
Teaches Groq what to redact and what to skip over time.
Stores in %LOCALAPPDATA%/ClaimFileRenamer/redaction_corrections.json.
"""
import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

_MAX_CORRECTIONS = 200


def _store_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path.home() / ".local" / "share"
    d = base / "ClaimFileRenamer"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _store_path() -> Path:
    return _store_dir() / "redaction_corrections.json"


def _load() -> list:
    path = _store_path()
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save(corrections: list):
    try:
        with open(_store_path(), "w", encoding="utf-8") as f:
            json.dump(corrections[-_MAX_CORRECTIONS:], f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.debug("Failed to save redaction corrections: %s", e)


def log_redaction_correction(document_type: str, text_fragment: str, action: str):
    """Log a redaction correction asynchronously.
    action: 'should_redact' or 'should_not_redact'
    """
    def _write():
        try:
            corrections = _load()
            corrections.append({
                "document_type": document_type,
                "text_fragment": text_fragment,
                "action": action,
                "timestamp": datetime.now().isoformat(),
            })
            _save(corrections)
            # Sync to GitHub
            try:
                from src.services.github_sync import github_sync
                if github_sync.is_available():
                    computer = os.environ.get("COMPUTERNAME", "unknown")
                    # Upload as a separate file from classification corrections
                    path = _store_path()
                    if path.exists():
                        github_sync.upload_corrections(str(path))
            except Exception:
                pass
        except Exception as e:
            logger.debug("Failed to log redaction correction: %s", e)

    threading.Thread(target=_write, daemon=True).start()


def get_recent_corrections(n: int = 20) -> List[dict]:
    """Get the N most recent redaction corrections for few-shot prompting."""
    corrections = _load()
    return corrections[-n:]


def build_redaction_few_shot() -> str:
    """Build few-shot examples string for the Groq redaction prompt."""
    corrections = get_recent_corrections(20)
    if not corrections:
        return ""

    should_lines = []
    should_not_lines = []
    for c in corrections:
        text = c.get("text_fragment", "")
        if not text:
            continue
        if c.get("action") == "should_redact":
            should_lines.append(f'  - "{text}"')
        elif c.get("action") == "should_not_redact":
            should_not_lines.append(f'  - "{text}"')

    parts = []
    if should_lines:
        parts.append("Text that SHOULD be redacted (learned from corrections):\n" + "\n".join(should_lines[:10]))
    if should_not_lines:
        parts.append("Text that should NOT be redacted (learned from corrections):\n" + "\n".join(should_not_lines[:10]))
    return "\n\n".join(parts)
