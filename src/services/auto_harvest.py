"""
Automatic daily harvest of corrections from GitHub sync branch.
Downloads all staff corrections, merges them, and updates learned examples.
"""
import json
import logging
import os
import shutil
import tempfile
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)


def _app_data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path.home() / ".local" / "share"
    d = base / "ClaimFileRenamer"
    d.mkdir(parents=True, exist_ok=True)
    return d


class AutoHarvester:

    def should_run_today(self) -> bool:
        ts_file = _app_data_dir() / "last_harvest.txt"
        if not ts_file.exists():
            return True
        try:
            last = ts_file.read_text().strip()
            return last != date.today().isoformat()
        except Exception:
            return True

    def run_harvest(self) -> dict:
        result = {"files_read": 0, "new_examples": 0, "total_examples": 0, "ran_at": ""}
        try:
            from src.services.github_sync import github_sync
            from src.services.seed_examples import SEED_EXAMPLES

            # Download all corrections from GitHub
            tmp_dir = tempfile.mkdtemp(prefix="claimsco_harvest_")
            downloaded = []
            try:
                if github_sync.is_available():
                    downloaded = github_sync.download_all_corrections(tmp_dir)
            except Exception as e:
                logger.debug("Harvest download failed: %s", e)

            # Also include local corrections
            local_path = _app_data_dir() / "corrections.json"
            if local_path.exists():
                downloaded.append(str(local_path))

            # Merge all corrections
            all_corrections = []
            for fpath in downloaded:
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    corrections = data.get("corrections", [])
                    all_corrections.extend(corrections)
                    result["files_read"] += 1
                except Exception:
                    continue

            # Filter to corrections with non-empty fields_corrected
            useful = [c for c in all_corrections if c.get("fields_corrected")]

            # Deduplicate by filename + corrected_result (keep most recent)
            seen = {}
            for c in useful:
                key = c.get("original_filename", "")
                seen[key] = c  # later entry overwrites earlier

            # Build examples from corrections
            correction_examples = []
            for c in seen.values():
                correction_examples.append({
                    "filename": c.get("original_filename", ""),
                    "result": c.get("corrected_result", {}),
                })

            # Merge with existing seed examples
            existing_filenames = {ex["filename"] for ex in SEED_EXAMPLES}
            new_examples = [
                ex for ex in correction_examples
                if ex["filename"] not in existing_filenames
            ]

            merged = list(SEED_EXAMPLES) + new_examples

            # Deduplicate merged by filename
            seen_fn = set()
            unique = []
            for ex in merged:
                fn = ex.get("filename", "")
                if fn not in seen_fn:
                    seen_fn.add(fn)
                    unique.append(ex)

            # Keep 50 most diverse (simple: keep all up to 50)
            final = unique[:50]

            result["new_examples"] = len(new_examples)
            result["total_examples"] = len(final)

            # Write to learned_examples.json (works for both source and PyInstaller)
            learned_path = _app_data_dir() / "learned_examples.json"
            with open(learned_path, "w", encoding="utf-8") as f:
                json.dump(final, f, indent=2, ensure_ascii=False)

            # If running from source, also try to update seed_examples.py
            import sys
            if not getattr(sys, "frozen", False):
                try:
                    seed_path = os.path.join(
                        os.path.dirname(os.path.abspath(__file__)),
                        "seed_examples.py"
                    )
                    lines = [
                        '"""\n',
                        'Seed examples for Groq few-shot classification.\n',
                        'Updated periodically by harvest_corrections.py from staff corrections.\n',
                        '"""\n\n',
                        'SEED_EXAMPLES = [\n',
                    ]
                    for ex in final:
                        lines.append(f'    {json.dumps(ex, ensure_ascii=False)},\n')
                    lines.append(']\n')
                    with open(seed_path, "w", encoding="utf-8") as f:
                        f.writelines(lines)
                except Exception as e:
                    logger.debug("Could not update seed_examples.py: %s", e)

            # Record harvest date
            ts_file = _app_data_dir() / "last_harvest.txt"
            today_str = date.today().isoformat()
            ts_file.write_text(today_str)
            result["ran_at"] = today_str

            # Clean up temp dir (but not local corrections)
            try:
                if os.path.exists(tmp_dir):
                    shutil.rmtree(tmp_dir)
            except Exception:
                pass

        except Exception as e:
            logger.debug("Harvest failed: %s", e)

        return result


auto_harvester = AutoHarvester()
