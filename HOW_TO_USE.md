# Claim File Renamer — Team How-To Guide

## What This App Does

Claim File Renamer is a **local desktop application** (Windows) that bulk-renames insurance claim and AFCA PDF documents into a standardised format:

```
WHO - DATE - ENTITY - WHAT.pdf
```

Examples:
```
FF - 11.04.2024 - Campbell Constructions - Site Report.pdf
Complainant - 23.02.2024 - ACB - Letter of Engagement.pdf
AFCA - 03.06.2025 - Request for Information.pdf
FF - NO DATE - Sedgwick - Assessment Report.pdf
```

Everything runs locally on your machine — no files are uploaded anywhere.

---

## 1. Getting the App

### Option A — Use the Built Executable (Recommended)

1. Download the ZIP of the project from GitHub:
   - Go to `https://github.com/nicholasgoss1/documentnamingapp`
   - Switch to the branch **`claude/generate-runnable-project-HDg4G`**
   - Click the green **Code** button → **Download ZIP**
2. Extract the ZIP to a folder on your PC (e.g. `C:\ClaimFileRenamer`)
3. Open a Command Prompt in that folder and run:
   ```
   packaging\build_windows.bat
   ```
   This creates `dist\ClaimFileRenamer\ClaimFileRenamer.exe`.
4. Double-click `ClaimFileRenamer.exe` to launch.

### Option B — Run from Source (Developer)

1. Install **Python 3.12+** from [python.org](https://www.python.org/downloads/)
2. Download/clone the repo as above
3. Open a Command Prompt in the project folder and run:
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   python main.py
   ```

---

## 2. Prepare Your Files

- Gather the **PDF files** you want to rename into a folder on your PC.
- Only `.pdf` files are supported.
- The app works best with text-based PDFs. Scanned image PDFs will have limited metadata extraction (no OCR).

---

## 3. Load Files into the App

You have two options:

- **Drag and drop** — Drag PDF files or an entire folder onto the app window.
- **File menu** — Click **File → Open Files** (Ctrl+O) and select your PDFs.

A progress bar will appear as the app processes each file.

---

## 4. What the App Does Automatically

For each PDF, the app extracts and infers:

| Field | What It Means | Example Values |
|---|---|---|
| **WHO** | Who the document is from | FF, Complainant, AFCA, UNKNOWN |
| **DATE** | Document date | 11.04.2024, mm.yyyy, NO DATE |
| **ENTITY** | Company or person name | Sedgwick, QBE, ACB |
| **WHAT** | Document type | Site Report, Assessment Report, Quote |

It also calculates:
- **Confidence score** (0–100) — how certain the app is about its guesses
- **Duplicate status** — flags exact duplicates, likely duplicates, and name collisions

The app then generates a **Proposed Filename** in the format `WHO - DATE - ENTITY - WHAT.pdf`.

---

## 5. Review and Edit

The main table shows all loaded files with 10 columns. Here's what to look at:

### Check Confidence

- **Green** = high confidence, likely correct
- **Amber** = low confidence (below 60%), review carefully
- The **Confidence Reason** column tells you why confidence is low

### Edit Fields

- **Double-click** any cell in the WHO, DATE, ENTITY, or WHAT columns to edit it
- The Proposed Filename updates automatically when you change a field

### Bulk Editing (for multiple files)

Select multiple rows (Ctrl+Click or Shift+Click), then use the toolbar buttons:

| Button | What It Does |
|---|---|
| **Set WHO** | Set WHO for all selected rows |
| **Set Entity** | Set ENTITY for all selected rows |
| **Set WHAT** | Set document type for all selected rows |
| **Set Date** | Set DATE for all selected rows |
| **No Date** | Mark all selected as "NO DATE" |
| **Find/Replace** | Find and replace text across fields |

### Filter Problem Files

Use the **filter checkboxes** at the top to quickly find files that need attention:

- **Low Conf** — confidence below 60%
- **NO DATE** — missing date
- **No WHO** — missing WHO field
- **No WHAT** — missing document type
- **Duplicates** — flagged as duplicate
- **Annexure** — detected annexure wrapper

### Preview PDFs

Click any row to see a preview of the PDF in the right-hand pane.

---

## 6. Approve and Rename

### Step 1: Approve

- Select the rows you're happy with and click **Approve Selected** (Ctrl+A)
- Or click **Approve All** to approve everything visible

The Status column changes from PENDING → APPROVED.

### Step 2: Rename

- Click **Rename Approved**
- The app validates all approved files (checks for duplicate names, invalid characters, path length)
- If valid, files are renamed **in place** in their original folder

The Status column changes from APPROVED → RENAMED (shown in green).

### If Something Goes Wrong

- **Undo Last Batch** (Ctrl+Z or the Undo button) — reverts all files from the last rename back to their original names
- The app saves a rollback manifest automatically, so you can always undo

---

## 7. Export Results

- **File → Export CSV** (Ctrl+E) — saves a spreadsheet of all files with their original names, proposed names, confidence scores, and rename status
- Exports are saved to `%LOCALAPPDATA%\ClaimFileRenamer\exports\`

---

## 8. Handling Duplicates

The app automatically detects:

- **Exact Duplicates** — identical files (same content). The second copy gets " - DUPLICATE" appended to its proposed filename.
- **Likely Duplicates** — same text content but different file hash (e.g. re-saved PDF).
- **Name Collisions** — different files that would end up with the same proposed filename.

Use the **Duplicates** filter checkbox to review all flagged files before renaming.

---

## 9. Settings

Access via **Edit → Settings** or the gear icon.

Key settings:

| Setting | What It Controls |
|---|---|
| **Dark Mode** | Toggle dark/light theme (also in View menu) |
| **Confidence Threshold** | Below this score, files are marked UNSURE (default: 60) |
| **Strip Annexure Prefix** | Auto-remove "Annexure X" wrappers from filenames |
| **Entity Aliases** | Map variations to a standard name (e.g. "Campbell Construction" → "Campbell Constructions") |
| **Preferred Entities** | Your common entity names for quick selection |
| **Preferred Doc Labels** | Your standard document type labels |

Settings persist between sessions in `%LOCALAPPDATA%\ClaimFileRenamer\settings.json`.

---

## Quick Reference

| Action | Shortcut |
|---|---|
| Open files | Ctrl+O |
| Approve selected | Ctrl+A |
| Undo last rename | Ctrl+Z |
| Export CSV | Ctrl+E |
| Toggle dark mode | View → Toggle Dark Mode |

---

## Troubleshooting

| Problem | Solution |
|---|---|
| App won't start | Make sure Python 3.12+ is installed, or use the built .exe |
| "No text extracted" | The PDF is likely a scanned image — edit fields manually |
| Confidence is low on everything | Check Settings → entity aliases and doc type keywords are configured for your documents |
| Rename fails | Check the error message — common causes: file is open in another program, path too long, invalid characters |
| Need to undo a rename | Edit → Undo Last Batch (Ctrl+Z) — works for the most recent batch only |

---

## Files and Folders

| Location | Contents |
|---|---|
| `%LOCALAPPDATA%\ClaimFileRenamer\settings.json` | Your saved settings |
| `%LOCALAPPDATA%\ClaimFileRenamer\logs\` | Rename operation logs |
| `%LOCALAPPDATA%\ClaimFileRenamer\rollback\` | Undo manifests |
| `%LOCALAPPDATA%\ClaimFileRenamer\exports\` | CSV exports |
