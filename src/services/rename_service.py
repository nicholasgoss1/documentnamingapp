"""
Batch rename service with rollback support.
All operations are local filesystem only.
"""
import json
import os
import shutil
import csv
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from src.core.models import DocumentRecord, RenameStatus
from src.core.settings import get_rollback_dir, get_exports_dir, get_logs_dir


def validate_rename(record: DocumentRecord) -> Tuple[bool, str]:
    """Validate a single rename operation before executing."""
    if not record.proposed_filename:
        return False, "No proposed filename"
    if not record.proposed_filename.lower().endswith(".pdf"):
        return False, "Filename must end with .pdf"
    if not record.file_path or not os.path.exists(record.file_path):
        return False, f"Source file not found: {record.file_path}"

    # Check for invalid Windows characters
    invalid = '<>:"/\\|?*'
    name_part = record.proposed_filename[:-4]  # Strip .pdf
    for ch in invalid:
        if ch in name_part:
            return False, f"Invalid character '{ch}' in filename"

    # Check for empty components (repeated separators)
    if " -  - " in record.proposed_filename or " - .pdf" == record.proposed_filename[-7:]:
        return False, "Malformed filename with empty components"

    # Check length (Windows MAX_PATH)
    target_dir = os.path.dirname(record.file_path)
    target_path = os.path.join(target_dir, record.proposed_filename)
    if len(target_path) > 255:
        return False, "Full path exceeds 255 characters"

    return True, ""


def validate_batch(records: List[DocumentRecord]) -> List[Tuple[int, str]]:
    """Validate all records. Returns list of (index, error_message) for failures."""
    errors = []
    # Check for duplicate target names
    target_names = {}
    for i, rec in enumerate(records):
        if rec.rename_status != RenameStatus.APPROVED:
            continue
        valid, msg = validate_rename(rec)
        if not valid:
            errors.append((i, msg))
            continue
        lower_name = rec.proposed_filename.lower()
        if lower_name in target_names:
            errors.append((i, f"Duplicate target name with row {target_names[lower_name]}"))
        else:
            target_names[lower_name] = i

    return errors


def execute_rename_batch(records: List[DocumentRecord]) -> Tuple[int, int, str]:
    """
    Execute rename for all approved records.
    Returns (success_count, error_count, rollback_manifest_path).
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    manifest_path = get_rollback_dir() / f"rollback_{timestamp}.json"
    log_path = get_logs_dir() / f"rename_log_{timestamp}.txt"

    manifest = {
        "timestamp": timestamp,
        "operations": []
    }

    success = 0
    errors = 0

    with open(log_path, "w", encoding="utf-8") as log_file:
        log_file.write(f"Rename batch started: {datetime.now().isoformat()}\n\n")

        for i, rec in enumerate(records):
            if rec.rename_status != RenameStatus.APPROVED:
                continue

            source = rec.file_path
            target_dir = os.path.dirname(source)
            target = os.path.join(target_dir, rec.proposed_filename)

            # Check if target already exists
            if os.path.exists(target) and os.path.abspath(source) != os.path.abspath(target):
                rec.rename_status = RenameStatus.ERROR
                rec.error_message = "Target file already exists"
                errors += 1
                log_file.write(f"ERROR [{i}]: {source} -> {target} (target exists)\n")
                continue

            try:
                os.rename(source, target)
                rec.rename_status = RenameStatus.RENAMED
                rec.new_file_path = target
                manifest["operations"].append({
                    "index": i,
                    "original_path": source,
                    "new_path": target,
                    "original_filename": rec.original_filename,
                    "proposed_filename": rec.proposed_filename
                })
                success += 1
                log_file.write(f"OK [{i}]: {source} -> {target}\n")
            except OSError as e:
                rec.rename_status = RenameStatus.ERROR
                rec.error_message = str(e)
                errors += 1
                log_file.write(f"ERROR [{i}]: {source} -> {target} ({e})\n")

        log_file.write(f"\nCompleted: {success} renamed, {errors} errors\n")

    # Save rollback manifest
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return success, errors, str(manifest_path)


def undo_last_batch() -> Tuple[int, int, str]:
    """
    Undo the most recent rename batch using the rollback manifest.
    Returns (success_count, error_count, message).
    """
    rollback_dir = get_rollback_dir()
    manifests = sorted(rollback_dir.glob("rollback_*.json"), reverse=True)
    if not manifests:
        return 0, 0, "No rollback manifest found"

    manifest_path = manifests[0]
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    success = 0
    errors = 0

    for op in reversed(manifest.get("operations", [])):
        new_path = op["new_path"]
        original_path = op["original_path"]
        try:
            if os.path.exists(new_path):
                os.rename(new_path, original_path)
                success += 1
            else:
                errors += 1
        except OSError:
            errors += 1

    # Remove the used manifest
    try:
        os.remove(manifest_path)
    except OSError:
        pass

    return success, errors, f"Undone {success} renames, {errors} errors"


def export_csv(records: List[DocumentRecord], filepath: str = None) -> str:
    """Export rename log to CSV."""
    if filepath is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = str(get_exports_dir() / f"rename_export_{timestamp}.csv")

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Original Filename", "WHO", "DATE", "ENTITY", "WHAT",
            "Proposed Filename", "Confidence", "Confidence Reasons",
            "Duplicate Status", "Rename Status", "Error", "File Path"
        ])
        for rec in records:
            writer.writerow([
                rec.original_filename,
                rec.who,
                rec.date,
                rec.entity,
                rec.what,
                rec.proposed_filename,
                rec.confidence,
                rec.confidence_breakdown.reasons() if rec.confidence_breakdown else "",
                rec.duplicate_status.value if rec.duplicate_status else "",
                rec.rename_status.value if rec.rename_status else "",
                rec.error_message,
                rec.file_path
            ])

    return filepath


def get_rename_history() -> List[dict]:
    """Load all rollback manifests for history viewing."""
    rollback_dir = get_rollback_dir()
    manifests = sorted(rollback_dir.glob("rollback_*.json"), reverse=True)
    history = []
    for mp in manifests:
        try:
            with open(mp, "r", encoding="utf-8") as f:
                data = json.load(f)
                data["manifest_path"] = str(mp)
                history.append(data)
        except (json.JSONDecodeError, OSError):
            pass
    return history
