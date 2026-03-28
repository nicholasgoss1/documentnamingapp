# ClaimsCo Document Tools

A local-first Windows desktop app for insurance claim document processing.

## Download

**Latest installer (always up to date):**
https://github.com/nicholasgoss1/documentnamingapp/releases/latest/download/ClaimsCo_Tools_Setup_latest.exe

Existing staff: you do not need to re-download for AI improvements.
These are delivered silently every time you open the app.
Only download again if the app shows "App update available" in the status bar.

---

## Three Tools in One

The app has three tabs:

**Tab 1 — Document Renamer**
Bulk-renames insurance claim PDFs into ClaimsCo's standard naming format:
`WHO - DATE - ENTITY - WHAT.pdf`
AI-assisted classification with inline editing, PDF preview, and rollback.

**Tab 2 — Privacy Redaction**
Scans PDFs for personally identifiable information (names, phone numbers, policy numbers, addresses) and replaces them with anonymised tokens like `[CLIENT_ID_001]`. Export a redacted text pack and view the full token map.

**Tab 3 — Claude Extraction Pack**
Groq-assisted verbatim extraction for AFCA submission drafting. Generates a structured Verbatim Pack with VP1–VP6 sections from matter folder PDFs, ready for upload to Claude AFCA Assistant v24.

---

## AI-Enhanced Classification

- Uses **Groq free tier** with the `llama-3.1-8b-instant` model
- **14,400 classifications per day** (shared across all users on the free tier)
- Only called when rule-based confidence is below 75% — most documents are classified locally without any API calls
- Falls back to fully offline rule-based classification automatically if Groq is unavailable
- 8-second timeout per call — never blocks the app
- API key is configured in `src/services/ai_classifier.py`

## Privacy Redaction

- **Fully local processing** — nothing is sent externally
- Uses spaCy `en_core_web_sm` for person name detection (2+ word names only)
- Regex patterns for Australian phone numbers, policy numbers, and street addresses
- Token format: `[CLIENT_ID_001]`, `[CLIENT_ID_002]`, etc.
- Optional Groq second-pass detection for PII missed by the primary scan

## Claude Extraction Pack

- Groq-assisted smart extraction understands document types and pulls relevant passages
- VP1: PDS clause sections
- VP2: Complainant expert report conclusions and methodology
- VP3: FF decisions and decline reasons
- VP4: Builder/engineer scope methodology notes
- VP5: Weather evidence key data passages
- VP6: Solar and specialist technical reports
- Falls back to raw text extraction when Groq is unavailable
- Missing section warnings help identify gaps in evidence

---

## Setup

### Quick setup (recommended)

1. Double-click `ClaimsCo_Tools_Setup.bat`
2. It will install all Python dependencies automatically.
3. Optionally install Tesseract and Poppler (see below).
4. For spaCy NER: `python -m spacy download en_core_web_sm`

### Manual setup

```
pip install -r requirements.txt
python -m spacy download en_core_web_sm
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

```
python main.py
```

Or run `src/ui/main_window.py` directly:
```
python -c "from src.ui.main_window import MainWindow; from src.core.settings import Settings; from PySide6.QtWidgets import QApplication; import sys; app = QApplication(sys.argv); w = MainWindow(Settings()); w.show(); sys.exit(app.exec())"
```

---

## Privacy and data handling

- **Tab 1**: All rule-based processing is fully local. When Groq AI is enabled, the first 1200 characters of extracted text are sent to Groq's API for low-confidence documents only.
- **Tab 2**: All spaCy/regex processing is fully local. Optional Groq second-pass sends already-redacted text only.
- **Tab 3**: Document text is sent to Groq for intelligent extraction. Falls back to local-only raw text extraction when Groq is unavailable.
- The app does not collect analytics or phone home.

---

## Supported file types

- PDF (`.pdf`) — all tabs
- TXT (`.txt`) — Tab 1 renaming
- DOCX (`.docx`) — Tab 1 renaming
- Scanned PDFs are supported if Tesseract OCR and Poppler are installed.

---

## File structure

```
main.py                    Entry point
src/core/                  Data models and settings
src/services/              Classification, extraction, AI services
src/ui/                    PySide6 GUI (main_window, tabs, dialogs)
assets/                    Icons and logo
packaging/                 PyInstaller and Inno Setup files
tests/                     Unit tests
```

---

## Troubleshooting

**"ModuleNotFoundError: No module named 'PySide6'"**
Run `ClaimsCo_Tools_Setup.bat` or `pip install -r requirements.txt`.

**"AI: Offline (rule-based only)"**
The Groq API key is not configured. Edit `src/services/ai_classifier.py` and replace `gsk_PASTE_YOUR_KEY_HERE` with your Groq API key.

**Tab 2 shows "spaCy not available"**
Run `python -m spacy download en_core_web_sm`.

**App is slow on large folders**
All long-running operations run in background threads — the UI stays responsive.
Groq extraction adds ~5-15 seconds per document.
