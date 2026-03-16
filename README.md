# Claim File Renamer v1.0.0

A local-first bulk PDF renaming desktop application for insurance claim and AFCA documents. Built for Windows 11 with Python and PySide6.

**Privacy**: All processing is 100% local. No cloud backend. No file uploads. Works fully offline.

---

## Architecture Summary

```
main.py                          Entry point
src/
  core/
    settings.py                  JSON settings in %LOCALAPPDATA%\ClaimFileRenamer
    models.py                    DocumentRecord, Who, DuplicateStatus, etc.
  services/
    pdf_extractor.py             PyMuPDF text extraction, page render, file hash
    date_engine.py               Document-type-specific date inference
    classifier.py                WHO / ENTITY / WHAT inference
    normalizer.py                Filename cleanup, alias resolution, title case
    confidence.py                Confidence scoring with breakdown
    duplicate_detector.py        Binary, content, and name collision detection
    rename_service.py            Safe rename, rollback manifest, CSV export
    inference_pipeline.py        Orchestrator: processes PDFs end-to-end
  ui/
    main_window.py               Main window with drag-drop, table, actions
    table_model.py               Qt table model for DocumentRecords
    filter_proxy.py              Multi-criteria filter proxy
    preview_widget.py            PDF page preview
    worker.py                    Background processing thread
    settings_dialog.py           Rules editor dialog
    history_dialog.py            Rename history viewer
    theme.py                     Dark/light theme stylesheets
assets/
  icon.png / icon.ico            App icons
  generate_icon.py               Icon generator script
packaging/
  build_windows.bat              One-click Windows build script
  installer.iss                  Inno Setup installer script
  version_info.txt               Windows version resource
tests/
  test_date_engine.py            Date inference tests
  test_classifier.py             WHO/ENTITY/WHAT tests
  test_normalizer.py             Normalisation tests
  test_models.py                 Data model tests
  test_duplicate_detector.py     Duplicate detection tests
  create_test_pdfs.py            Generate sample test PDFs
```

---

## Folder Structure

```
documentnamingapp/
├── main.py
├── requirements.txt
├── build.spec
├── .gitignore
├── README.md
├── assets/
│   ├── icon.png
│   ├── icon.ico
│   └── generate_icon.py
├── packaging/
│   ├── build_windows.bat
│   ├── installer.iss
│   └── version_info.txt
├── src/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   └── models.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── pdf_extractor.py
│   │   ├── date_engine.py
│   │   ├── classifier.py
│   │   ├── normalizer.py
│   │   ├── confidence.py
│   │   ├── duplicate_detector.py
│   │   ├── rename_service.py
│   │   └── inference_pipeline.py
│   └── ui/
│       ├── __init__.py
│       ├── main_window.py
│       ├── table_model.py
│       ├── filter_proxy.py
│       ├── preview_widget.py
│       ├── worker.py
│       ├── settings_dialog.py
│       ├── history_dialog.py
│       └── theme.py
└── tests/
    ├── __init__.py
    ├── test_date_engine.py
    ├── test_classifier.py
    ├── test_normalizer.py
    ├── test_models.py
    ├── test_duplicate_detector.py
    └── create_test_pdfs.py
```

---

## Setup Instructions (Developer / Maintainer)

### Prerequisites
- Windows 11
- Python 3.12+ installed (from python.org)
- Git (optional, for version control)

### Initial Setup
```cmd
cd documentnamingapp
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Run from source
```cmd
venv\Scripts\activate
python main.py
```

### Run tests
```cmd
venv\Scripts\activate
python -m pytest tests/ -v
```

### Generate test PDFs
```cmd
venv\Scripts\activate
python tests/create_test_pdfs.py
```

---

## Step-by-Step Windows 11 Packaging Instructions

### Option A: One-click build (recommended)
```cmd
packaging\build_windows.bat
```
This creates:
- `dist\ClaimFileRenamer\` - portable folder with exe
- `installer_output\ClaimFileRenamer_Setup_1.0.0.exe` - installer (if Inno Setup installed)

### Option B: Manual build steps

#### 1. Build the executable
```cmd
venv\Scripts\activate
pyinstaller build.spec --clean --noconfirm
```
Output: `dist\ClaimFileRenamer\ClaimFileRenamer.exe`

#### 2. Test the build
Run `dist\ClaimFileRenamer\ClaimFileRenamer.exe` and verify:
- Window opens with dark theme
- Drag and drop PDFs works
- PDF preview renders
- Settings dialog opens
- Rename workflow completes

#### 3. Create the installer (requires Inno Setup)
1. Download Inno Setup from https://jrsoftware.org/isdl.php
2. Install it (adds `iscc` to PATH)
3. Run:
```cmd
iscc packaging\installer.iss
```
Output: `installer_output\ClaimFileRenamer_Setup_1.0.0.exe`

### Recommended distribution format
**Installer .exe** is recommended for non-technical staff because:
- Single file to distribute
- Standard Windows install/uninstall experience
- Creates Start Menu and optional Desktop shortcuts
- No need to explain folder extraction

The portable folder (`dist\ClaimFileRenamer\`) is useful for:
- Testing before creating installer
- USB distribution
- Users who prefer portable apps

---

## Step-by-Step Testing Instructions

### 1. Generate test data
```cmd
python tests/create_test_pdfs.py
```
This creates 22 sample PDFs in `tests/test_pdfs/`.

### 2. Run unit tests
```cmd
python -m pytest tests/ -v
```

### 3. Manual integration test
1. Launch the app: `python main.py`
2. Drag the `tests/test_pdfs/` folder into the window
3. Wait for processing (progress bar)
4. Verify proposed filenames match expected results (see below)
5. Try editing a WHO field inline
6. Try bulk-setting ENTITY on selected rows
7. Filter by "UNSURE" to see low-confidence files
8. Click a row to see PDF preview
9. Approve all, then rename
10. Check the rename log in `%LOCALAPPDATA%\ClaimFileRenamer\logs\`
11. Click Undo Last Batch
12. Verify files are restored to original names

---

## Sample Test Dataset and Expected Filenames

| Original Filename | Expected Renamed Filename |
|---|---|
| Annexure 1.pdf | FF - 11.04.2024 - Campbell Constructions - Site Report.pdf |
| Annexure 2.pdf | FF - NO DATE - Campbell Constructions - Photo Schedule.pdf |
| Sedgwick_Assessment_14032024.pdf | FF - 14.03.2024 - Sedgwick - Assessment Report.pdf |
| Progress_Rpt_1.pdf | FF - 11.04.2024 - Sedgwick - Progress Report 1.pdf |
| Progress_Update_2.pdf | FF - 19.06.2024 - Sedgwick - Progress Report 2.pdf |
| Morse_Roof_Rpt.pdf | FF - 10.06.2024 - Morse Building Consultants - Roof Report.pdf |
| QBE_Decision_25062024.pdf | FF - 25.06.2024 - QBE - IDR FDL.pdf |
| AFCA_RFI_03062025.pdf | AFCA - 03.06.2025 - Request for Information.pdf |
| AFCA_WPA.pdf | AFCA - 23.07.2025 - Written Preliminary Assessment.pdf |
| ACB_Report_Final.pdf | Complainant - 06.02.2024 - ACB - Building Report.pdf |
| ACB_Supp_Report.pdf | Complainant - 18.12.2025 - ACB - Supplementary Report.pdf |
| LOE_signed.pdf | Complainant - 23.02.2024 - Letter of Engagement.pdf |
| COI_2023.pdf | Complainant - 15.11.2023 - COI - Certificate of Insurance.pdf |
| Policy_Schedule_2023.pdf | FF - 15.11.2023 - Policy Schedule.pdf |
| QBE_PDS_QM486-0323.pdf | FF - 03.2023 - PDS - QM486-0323.pdf |
| ACB_Quote_2024.pdf | Complainant - NO DATE - ACB - Quote - $57,987.80.pdf |
| Our_AFCA_Submission.pdf | Complainant - 04.12.2024 - AFCA Submission.pdf |
| Complainant_NOR.pdf | Complainant - 17.06.2025 - Notice of Response.pdf |
| QBE_NOR_23122024.pdf | FF - 23.12.2024 - Notice of Response from QBE.pdf |
| AAF_blank.pdf | Complainant - NO DATE - AAF to be signed.pdf |
| ACB_STAR.pdf | Complainant - 17.06.2025 - Supplementary Technical Assessment Report.pdf |
| claim_email_printout.pdf | Complainant - 06.03.2024 - Claim Lodgement Email.pdf |

---

## End-User Instructions

### Installing
1. Double-click `ClaimFileRenamer_Setup_1.0.0.exe`
2. If Windows SmartScreen appears, click "More info" then "Run anyway" (this is normal for internally-distributed software not signed with a commercial certificate)
3. Follow the installer prompts
4. Launch from Start Menu or Desktop shortcut

### Using the App
1. **Open the app** from Start Menu > Claim File Renamer
2. **Drag and drop** PDF files or a folder onto the app window
3. **Wait** for processing (progress bar shows status)
4. **Review** the proposed filenames in the table
5. **Edit** any field by double-clicking (WHO, DATE, ENTITY, WHAT)
6. **Filter** using the checkboxes (UNSURE, NO DATE, Duplicates, etc.)
7. **Preview** any PDF by clicking its row
8. **Bulk edit** by selecting multiple rows and using the bulk action buttons
9. **Approve** files (select + Approve Selected, or Approve All)
10. **Rename** by clicking "Rename Approved"
11. **Undo** if needed with "Undo Last Batch"
12. **Export** a CSV log via File > Export CSV

### Windows SmartScreen Guidance
When distributing internally, users may see a SmartScreen warning:
1. This appears because the app is not signed with a commercial code-signing certificate
2. Click **"More info"** on the SmartScreen dialog
3. Click **"Run anyway"**
4. This only appears on the first run

To avoid SmartScreen entirely, purchase an EV code-signing certificate (~$300-500/year) and sign the installer.

### Data Storage
All app data is stored locally in:
```
%LOCALAPPDATA%\ClaimFileRenamer\
  settings.json     - Your preferences and rules
  logs\             - Rename operation logs
  exports\          - CSV exports
  rollback\         - Undo manifests
```

---

## Release Checklist

- [ ] Run all unit tests: `python -m pytest tests/ -v`
- [ ] Generate test PDFs and do a full manual test
- [ ] Update version in `src/__init__.py`, `build.spec`, `packaging/installer.iss`, `packaging/version_info.txt`
- [ ] Build with PyInstaller: `pyinstaller build.spec --clean --noconfirm`
- [ ] Test the built exe from `dist\ClaimFileRenamer\`
- [ ] Build installer: `iscc packaging\installer.iss`
- [ ] Test installer on a clean Windows 11 machine
- [ ] Verify SmartScreen behavior
- [ ] Distribute `installer_output\ClaimFileRenamer_Setup_1.0.0.exe` to colleagues
- [ ] Include brief install instructions (see End-User Instructions above)

---

## v2 Roadmap

- [ ] OCR support for scanned/image-only PDFs (Tesseract integration)
- [ ] Regex-based custom rules engine for power users
- [ ] Linked-document date mode for photo schedules (inherit date from matched report)
- [ ] Batch processing profiles (save/load different rule sets per claim)
- [ ] Multi-claim support (process files across multiple claim folders)
- [ ] Auto-update mechanism for internal distribution
- [ ] Code-signing certificate for SmartScreen-free distribution
- [ ] Network folder support (UNC paths)
- [ ] Thumbnail grid view as alternative to table
- [ ] Plugin system for custom entity/doc-type recognisers
- [ ] Machine learning classifier trained on renamed file history
- [ ] Bulk PDF merge/split utilities
- [ ] Integration with document management systems
