"""
Corrections store — logs user edits to classification fields.
Stores corrections in %LOCALAPPDATA%/ClaimFileRenamer/corrections.json.
All operations are async-safe and never crash the app.
"""
import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_MAX_CORRECTIONS = 500


def _corrections_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path.home() / ".local" / "share"
    d = base / "ClaimFileRenamer"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _corrections_path() -> Path:
    return _corrections_dir() / "corrections.json"


def _archive_path() -> Path:
    return _corrections_dir() / "corrections_archive.json"


def _load_corrections() -> dict:
    path = _corrections_path()
    if not path.exists():
        return {"version": "1.0", "corrections": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "corrections" not in data:
            return {"version": "1.0", "corrections": []}
        return data
    except Exception as e:
        logger.debug("Failed to load corrections.json: %s", e)
        return {"version": "1.0", "corrections": []}


def _save_corrections(data: dict) -> bool:
    try:
        path = _corrections_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.debug("Failed to save corrections.json: %s", e)
        return False


def get_corrections_count() -> int:
    data = _load_corrections()
    return len(data.get("corrections", []))


def get_corrections_list() -> list:
    data = _load_corrections()
    return data.get("corrections", [])


def log_correction(
    original_filename: str,
    text_snippet: str,
    ai_result: dict,
    corrected_result: dict,
    fields_corrected: list,
):
    """Log a correction asynchronously. Never blocks, never crashes."""
    def _write():
        try:
            data = _load_corrections()
            corrections = data.get("corrections", [])

            record = {
                "timestamp": datetime.now().isoformat(),
                "original_filename": original_filename,
                "text_snippet": text_snippet[:200],
                "ai_result": ai_result,
                "corrected_result": corrected_result,
                "fields_corrected": fields_corrected,
            }
            corrections.append(record)

            # Cap at _MAX_CORRECTIONS — archive overflow
            if len(corrections) > _MAX_CORRECTIONS:
                overflow = corrections[:-_MAX_CORRECTIONS]
                corrections = corrections[-_MAX_CORRECTIONS:]

                # Append overflow to archive
                try:
                    archive_path = _archive_path()
                    if archive_path.exists():
                        with open(archive_path, "r", encoding="utf-8") as f:
                            archive = json.load(f)
                    else:
                        archive = {"version": "1.0", "corrections": []}
                    archive["corrections"].extend(overflow)
                    with open(archive_path, "w", encoding="utf-8") as f:
                        json.dump(archive, f, indent=2, ensure_ascii=False)
                except Exception as e:
                    logger.debug("Failed to archive corrections: %s", e)

            data["corrections"] = corrections
            _save_corrections(data)

            # Silent GitHub sync after save
            try:
                from src.services.github_sync import github_sync
                if github_sync.is_available():
                    sync_thread = threading.Thread(
                        target=github_sync.upload_corrections,
                        args=(str(_corrections_path()),),
                        daemon=True,
                    )
                    sync_thread.start()
            except Exception:
                pass

        except Exception as e:
            logger.debug("Failed to log correction: %s", e)

    thread = threading.Thread(target=_write, daemon=True)
    thread.start()


def lookup_by_filename(filename: str) -> Optional[dict]:
    """Exact filename match. Returns corrected_result or None."""
    data = _load_corrections()
    for c in reversed(data.get("corrections", [])):
        if c.get("original_filename") == filename:
            return c.get("corrected_result")
    return None


def lookup_by_entity_segment(entity: str) -> Optional[str]:
    """Find a correction where the entity segment matches. Returns the corrected entity or None."""
    if not entity:
        return None
    entity_lower = entity.lower()
    data = _load_corrections()
    for c in reversed(data.get("corrections", [])):
        corrected = c.get("corrected_result", {})
        if corrected.get("entity", "").lower() == entity_lower:
            return corrected["entity"]
        # Check if entity was in the fields_corrected
        if "entity" in c.get("fields_corrected", []):
            if corrected.get("entity", "").lower() == entity_lower:
                return corrected["entity"]
    return None


def get_few_shot_examples(n: int = 5) -> list:
    """Get the N most recent corrections with non-empty fields_corrected for few-shot prompting."""
    data = _load_corrections()
    examples = []
    for c in reversed(data.get("corrections", [])):
        if c.get("fields_corrected"):
            examples.append({
                "filename": c.get("original_filename", ""),
                "result": c.get("corrected_result", {}),
            })
            if len(examples) >= n:
                break
    return examples


def get_last_sync_time() -> str:
    """Return the last sync timestamp or 'Never'."""
    try:
        ts_file = _corrections_dir() / "last_sync.txt"
        if ts_file.exists():
            return ts_file.read_text().strip()
    except Exception:
        pass
    return "Never"


def set_last_sync_time():
    """Record the current time as last sync."""
    try:
        ts_file = _corrections_dir() / "last_sync.txt"
        ts_file.write_text(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    except Exception:
        pass


def get_last_harvest_time() -> str:
    """Return the last harvest timestamp or 'Never'."""
    try:
        ts_file = _corrections_dir() / "last_harvest.txt"
        if ts_file.exists():
            return ts_file.read_text().strip()
    except Exception:
        pass
    return "Never"
