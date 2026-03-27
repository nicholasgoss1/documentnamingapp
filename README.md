# ClaimsCo Document Tools

A local-first Windows desktop app for insurance claim document processing.
All processing happens on your machine — no data leaves the device.

---

## What it does

The app has three tabs:

**Tab 1 — Document Renaming**
Bulk-renames insurance claim PDFs into ClaimsCo's standard naming format:
`WHO - DATE - ENTITY - WHAT.pdf`
AI-assisted classification with inline editing, PDF preview, and rollback.

**Tab 2 — Privacy Redaction**
Redacts sensitive personal information from PDFs before sharing or extraction.
Redacted copies are saved to a `Redacted/` subfolder — originals are never touched.

**Tab 3 — PDF Extraction**
Extracts all PDFs in a matter folder into a single structured Master Evidence TXT file
ready for upload to Claude AFCA Assistant v24.

---

## Setup

### Quick setup (recommended)

1. Double-click `ClaimsCo_Tools_Setup.bat`
2. It will install all Python dependencies automatically.
3. Optionally install Tesseract and Poppler (see below).

### Manual setup

```
pip install -r requirements.txt
```

### Python version

Python 3.11 or later is required.
Download from: https://www.python.org/downloads/
(Tick "Add Python to PATH" during installation.)

---

## Optional: Tesseract OCR

Required only if your PDFs contain scanned pages (images rather than text).
Text-based PDFs work without it.

1. Download from: https://github.com/UB-Mannheim/tesseract/wiki
2. Install to the default path: `C:\Program Files\Tesseract-OCR\`

## Optional: Poppler

Required if you use Tesseract OCR.

1. Download from: https://github.com/oschwartz10612/poppler-windows/releases
2. Extract to `C:\poppler\` so the binaries are at `C:\poppler\Library\bin\`

---

## Running the app

Double-click `ClaimsCo_Tools.py`, or run:

```
python ClaimsCo_Tools.py
```

---

## How to use each tab

### Tab 1 — Document Renaming

1. Drag and drop PDF files onto the table, or use **File → Open Files**.
2. Review the AI-suggested names (WHO, DATE, ENTITY, WHAT columns).
3. Edit any field inline by clicking on it.
4. Use the bulk action toolbar to set fields across multiple rows.
5. Click **Approve Selected** or **Approve All**.
6. Click **Rename Approved** to rename files on disk.
7. Use **Undo Last Batch** to reverse if needed.

### Tab 2 — Privacy Redaction

1. Click **Browse Folder** and select your matter folder.
2. The app lists all PDFs found. All are checked by default.
3. Uncheck any files you do not want to redact.
4. Select which redaction rules to apply (all on by default).
5. Optionally add custom terms (names, policy numbers, etc.) in the text box.
6. Click **Preview Count** to see how many instances will be redacted.
7. Click **Redact Selected Files** when ready.
8. Redacted copies are saved to `[matter_folder]/Redacted/`.
9. A `redaction_log.txt` is saved in the same Redacted folder.

**Redaction rules available:**
- Australian names (Title Case word pairs)
- Mobile numbers (04xx xxx xxx)
- Landline numbers ((0x) xxxx xxxx)
- Street addresses
- Postcodes
- Email addresses
- Tax File Numbers (TFN)
- Medicare numbers
- Dates of birth
- BSB numbers
- Bank account numbers
- Policy numbers
- Claim numbers
- Custom terms (exact match)

### Tab 3 — PDF Extraction

1. Click **Browse Folder** and select your matter folder (or the `Redacted/` subfolder from Tab 2).
2. The inventory panel shows all PDFs and their classifications.
   Files identified as internal notes are marked `[SKIP]` and excluded automatically.
3. Click **Extract PDFs**.
4. The app processes each PDF and writes a Master Evidence TXT file to:
   `[matter_folder]/[FolderName]_MasterEvidence.txt`
5. Every page is formatted as a citation block:
   ```
   [SOURCE: filename.pdf | PAGE: N]
   ...page text...
   ────────────────────────────────────────────────────────────
   ```
6. The output includes a file inventory, all extracted content, and a token estimate.

**Files excluded automatically (internal notes):**
Filenames containing: `claim notes history`, `claim history notes`, `timeline`,
`internal notes`, `working notes`, `claimsco notes` (case-insensitive)

---

## Privacy and data handling

- **All processing is fully local.** No files, text, or metadata are ever sent to any server.
- **Tab 2**: Original files are never modified. Redacted copies are written to a separate subfolder.
- **Tab 3**: The output TXT file is saved to your local matter folder.
- The app does not phone home, collect analytics, or require internet access.

---

## Supported file types

- PDF (`.pdf`) — all tabs
- Scanned PDFs are supported in Tab 3 if Tesseract OCR and Poppler are installed.

---

## File structure

```
ClaimsCo_Tools.py          Main combined app (all three tabs)
requirements.txt           Python dependencies
ClaimsCo_Tools_Setup.bat   One-click Windows setup
README.md                  This file
main.py                    Original Claim File Renamer entry point (preserved)
src/                       Original Claim File Renamer source (preserved)
assets/                    Icons and logo
```

---

## Troubleshooting

**"ModuleNotFoundError: No module named 'pdfplumber'"**
Run `ClaimsCo_Tools_Setup.bat` or `pip install -r requirements.txt`.

**"Tesseract OCR not found"**
Install Tesseract from https://github.com/UB-Mannheim/tesseract/wiki.
The app still works for text-based PDFs without it.

**Tab 2 redaction produces no changes**
Ensure the PDF has a text layer (not a pure scan). Use Preview Count first.
Scanned PDFs require Tesseract + Poppler for OCR-based text location.

**App is slow on large folders**
All long-running operations run in background threads — the UI stays responsive.
Large matter folders (50+ PDFs) may take several minutes.
