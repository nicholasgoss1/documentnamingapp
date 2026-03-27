"""
Harvest corrections from GitHub sync branch and update seed examples.
Run by Nick only — does NOT auto-commit.

Usage: python harvest_corrections.py
"""
import json
import os
import sys
import tempfile
import shutil

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    print("=" * 60)
    print("CLAIMSCO CORRECTIONS HARVESTER")
    print("=" * 60)
    print()

    from src.services.github_sync import github_sync
    from src.services.seed_examples import SEED_EXAMPLES

    # Step 1: Download all corrections from GitHub
    print("Checking GitHub sync availability...")
    if github_sync.is_available():
        print("  GitHub sync: available")
    else:
        print("  GitHub sync: NOT available (no token found)")
        print("  Will use local corrections only.")

    tmp_dir = tempfile.mkdtemp(prefix="claimsco_harvest_")
    downloaded = []

    if github_sync.is_available():
        print("Downloading corrections from GitHub...")
        downloaded = github_sync.download_all_corrections(tmp_dir)
        print(f"  Downloaded {len(downloaded)} file(s) from corrections-sync branch")

    # Step 2: Also include local corrections
    local_dir = os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "ClaimFileRenamer"
    )
    local_path = os.path.join(local_dir, "corrections.json")
    if os.path.exists(local_path):
        downloaded.append(local_path)
        print(f"  Including local corrections: {local_path}")

    if not downloaded:
        print("\nNo corrections files found. Nothing to harvest.")
        return

    # Step 3: Merge all corrections
    all_corrections = []
    for fpath in downloaded:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            corrections = data.get("corrections", [])
            all_corrections.extend(corrections)
            print(f"  Read {len(corrections)} corrections from {os.path.basename(fpath)}")
        except Exception as e:
            print(f"  Error reading {fpath}: {e}")

    print(f"\nTotal corrections found: {len(all_corrections)}")

    # Step 4: Filter to useful corrections
    useful = [c for c in all_corrections if c.get("fields_corrected")]
    print(f"Corrections with field changes: {len(useful)}")

    # Step 5: Deduplicate by filename (keep most recent)
    seen = {}
    for c in useful:
        key = c.get("original_filename", "")
        seen[key] = c

    # Step 6: Build examples (anonymised — no text_snippet)
    correction_examples = []
    for c in seen.values():
        correction_examples.append({
            "filename": c.get("original_filename", ""),
            "result": c.get("corrected_result", {}),
        })

    # Step 7: Merge with existing SEED_EXAMPLES
    existing_filenames = {ex["filename"] for ex in SEED_EXAMPLES}
    new_examples = [
        ex for ex in correction_examples
        if ex["filename"] not in existing_filenames
    ]
    print(f"New examples (not already in seeds): {len(new_examples)}")

    merged = list(SEED_EXAMPLES) + new_examples

    # Deduplicate
    seen_fn = set()
    unique = []
    for ex in merged:
        fn = ex.get("filename", "")
        if fn not in seen_fn:
            seen_fn.add(fn)
            unique.append(ex)

    # Keep 50 most diverse
    final = unique[:50]
    print(f"Total seed examples after merge: {len(final)}")

    # Step 8: Write updated seed_examples.py
    seed_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "src", "services", "seed_examples.py"
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

    print(f"\nUpdated: {seed_path}")

    # Clean up temp dir
    try:
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)
    except Exception:
        pass

    # Step 9: Print git commands
    print()
    print("=" * 60)
    print("SUMMARY")
    print(f"  Corrections found: {len(all_corrections)}")
    print(f"  New examples added: {len(new_examples)}")
    print(f"  Total seed examples: {len(final)}")
    print(f"  Updated src/services/seed_examples.py")
    print()
    print("To commit these changes:")
    print('  git add src/services/seed_examples.py')
    print('  git commit -m "Update seed examples from corrections"')
    print('  git push')
    print("=" * 60)


if __name__ == "__main__":
    main()
