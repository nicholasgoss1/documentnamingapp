# ClaimsCo Document Tools — Source of Truth
**Last updated:** 28 March 2026
**Current version:** v2.1.2
**Maintained by:** Nick Goss, ClaimsCo Pty Ltd

---

## WHAT THIS APP IS

ClaimsCo Document Tools is a Windows desktop application for ClaimsCo Pty Ltd staff to process insurance claim PDF files for AFCA (Australian Financial Complaints Authority) dispute submissions. Three tools in one installer:

1. **Document Renamer** — bulk renames PDFs using ClaimsCo naming convention with Groq AI assist
2. **Privacy Redaction** — visually redacts PII from PDFs before sending to external AI tools
3. **Claude Extraction Pack** — extracts verbatim text sections into a structured Verbatim Pack file ready for Claude AFCA Assistant v24

---

## PROJECT LOCATIONS

| Item | Path |
|------|------|
| Project root | `C:\Projects\documentnamingapp` |
| GitHub repo | github.com/nicholasgoss1/documentnamingapp |
| Working branch | `claimsco-documents-manager` |
| Corrections sync branch | `corrections-sync` |
| Installer output | `C:\Projects\documentnamingapp\installer_output\` |
| Antivirus fallback | `C:\Projects\installer_out\` or `C:\Projects\installer_v[version]\` |
| Groq API key file | `C:\Projects\Groq API key.txt` |
| GitHub sync token file | `C:\Projects\GitHub sync token.txt` |

---

## VERSION HISTORY

| Version | Status | Key changes |
|---------|--------|-------------|
| 1.0–1.2 | Dead | Old "Claim File Renamer" branding |
| 2.0.0 | Dead | Wrong installer path, tabs broken |
| 2.0.1 | Dead | Tabs fixed, spaCy bundling broken |
| 2.0.2 | Dead | spaCy path fix attempt 1 — failed |
| 2.0.3 | Dead | spaCy path fix attempt 2 — failed |
| 2.0.4 | Dead | spaCy removed entirely, Groq PII detection, send-to-tab fixed |
| 2.0.5 | Dead | Corrections cache fix — confidence 100 on exact filename match |
| 2.0.6 | Dead | AI Redact button + redaction corrections learning loop |
| 2.0.7 | Dead | Bulk checkbox removal in Redactions panel |
| 2.0.8 | Dead | Checkbox visibility fix, write lock, atomic writes on corrections |
| 2.0.9 | Dead | Dollar amounts stripped from redaction document_type key |
| 2.1.0 | Dead | Editable Duplicate field, file list checkboxes Tab 2 + Tab 3 |
| 2.1.1 | Dead | Tab 3 Matter Details: Client Name / Address / Date of Loss auto-populate |
| 2.1.2 | **Current** | Client name extraction fix, date of loss Groq fallback, all Groq calls upgraded to llama-3.3-70b-versatile, smart matter corrections by value |

### What is in v2.1.2
- Client name regex fixed — no longer captures adjacent labels
- Date of Loss: broader regex patterns + Groq fallback if regex finds nothing
- All 7 Groq model references changed to llama-3.3-70b-versatile
- Matter corrections stored by filename AND extracted value — corrections apply globally across documents
- Tests: 64/65 passing (1 pre-existing failure: test_unsure_suffix)
- Committed: fb36b51+ on claimsco-documents-manager
- Installer size: 73MB

---

## INSTALLER RULES — NEVER BREAK THESE

```
AppId:   {4D574B20-DB46-4E5F-B09B-7F815975303B}
AppName: ClaimsCo Document Tools
```

**These two values must never change.** They are what Windows uses to silently replace old versions. If either changes, staff get two apps installed simultaneously.

Installer silently removes ALL previous versions including all "Claim File Renamer" versions (1.x) via registry wildcard search in `packaging/installer.iss [Code]` section.

**Version bump — always update all three files:**
- `src/core/settings.py` — APP_VERSION
- `packaging/installer.iss` — AppVersion, AppVerName, OutputBaseFilename
- `packaging/version_info.txt` — filevers, prodvers, FileVersion, ProductVersion

**Always commit and push BEFORE building installer.**

**Staff distribution:** Build locally, copy to network share. Do NOT send GitHub Releases URL to staff — browser downloads trigger Windows SmartScreen on unsigned exe. Local copy/share does not trigger SmartScreen.

---

## THREE-TAB ARCHITECTURE

### Tab 1 — Document Renamer

**Filename convention:**
```
[WHO] - [DD.MM.YYYY] - [ENTITY] - [WHAT].pdf
```

**WHO values:** Complainant, FF, AFCA, Unknown

**WHAT values:** Roof Report, IDR FDL, Quote, Scope of Repairs, Building Report, Supplementary Report, Letter of Engagement, Certificate of Insurance, PDS, AFCA Submission, Notice of Response, Photo Schedule, Solar Report, Solar Testing Report, Engineering Report, Scope of Works, Invoice, Agent Authority Form, Decline Letter, Desktop Assessment, Re-inspection Report, Policy Schedule, Claim Lodgement Email, Written Preliminary Assessment, Request for Information, Progress Report, Hail Report, Weather Report, Variation Report, Delegation of Authority

Note: WHAT can include dollar amounts e.g. "Quote $55,208.19" — this is correct and intentional.

**Classification pipeline:**
1. Check corrections.json — exact filename match returns confidence 100 immediately, skips all inference
2. Extract entity from filename third segment (confidence 0.90)
3. Rule-based classifier (date_engine.py, classifier.py, normalizer.py)
4. If confidence < 0.85: call Groq API (llama-3.3-70b-versatile)

**Duplicate field:** Editable dropdown — None / Exact Duplicate / Near Duplicate. Changes logged to corrections.json and synced to GitHub. Corrections cache checked before duplicate detection runs.

**Send button:** "Send to Privacy Redaction →" always visible, greyed out until files loaded

### Tab 2 — Privacy Redaction

Visual PDF redaction. Pages rendered at 150 DPI using PyMuPDF.

**spaCy has been permanently removed. Do not re-add it.**
Groq (llama-3.3-70b-versatile) handles all PII detection.

**Two separate redaction buttons:**

Regex Redact — offline, no Groq:
- Phones: `(\+?61[\s-]?)?(0\d[\s-]?)[\d\s-]{8,10}`
- Policy numbers: `[A-Z]{2,4}[-]?\d{6,12}`
- Full addresses: digits + street + suburb + STATE + postcode
- Street numbers including alphanumeric (17A, Unit 3, Lot 5)
- Label-value pairs: Name:, Address:, Client:, Insured:, etc.
- Reference numbers near labels: Job Number:, Claim No:, etc.

AI Redact — Groq only:
- Sends page text to Groq with last 20 redaction corrections as few-shot examples
- Returns list of PII strings, draws red-bordered boxes on canvas
- Boxes removable via Erase Box tool or bulk checkbox removal
- All boxes (red AI, black manual) become solid black on export
- Silent fail if Groq unavailable

**Redaction corrections learning:**
- Erase an AI box → logs should_not_redact to redaction_corrections.json
- Draw manual box over missed text → logs should_redact
- document_type key strips dollar amounts (e.g. "Quote" not "Quote $55,208.19")
- Synced to GitHub corrections-sync as redaction_corrections_[COMPUTERNAME].json

**File list panel (top right):**
- Shows all loaded files with checkboxes
- Select All / Deselect All toggle
- Remove Selected button removes checked files without clearing all

**Redactions panel (right):**
- Lists all redaction boxes with checkboxes: Page X [AI/Manual/Regex] "text"
- Select All / Deselect All toggle
- Remove Selected bulk-removes checked boxes, logs corrections for AI boxes

**Export:** `page.add_redact_annot()` + `doc.apply_redactions()` removes underlying text. Saves as `[name]_REDACTED.pdf`. Never modifies originals.

**Send button:** "Send to Claude Extraction Pack →" always visible, passes file paths to Tab 3

### Tab 3 — Claude Extraction Pack

Generates structured Verbatim Pack for Claude AFCA Assistant v24.

**Inputs:** PDFs + Client Name + Client Address + Date of Loss

**Matter Details auto-population:**
- On file load, scans first 2 pages of each PDF
- Regex searches for: Name:, Client:, Insured:, Customer:, Address:, Date of Loss:, Loss Date:, Event Date:, Claim Date:
- Groq fallback (llama-3.3-70b-versatile): if regex finds nothing, sends first 2000 chars to Groq, 8s timeout, silent fail
- Fields remain editable — user can correct any value
- Corrections stored by filename AND extracted value — bad extractions are auto-corrected globally on future loads
- Synced to GitHub as matter_corrections_[COMPUTERNAME].json

**File list panel (top right):**
- Shows all loaded files with checkboxes
- Select All / Deselect All toggle
- Remove Selected removes files from extraction queue

**VP sections:**
- VP1: PDS quotable clauses
- VP2: Complainant expert report conclusions/methodology
- VP3: FF expert reports and decision letters
- VP4: Scopes of works and quotes (both sides)
- VP5: Weather evidence
- VP6: Solar and specialist reports

**SmartExtractor routing:** classifies each doc then routes to correct extraction method. 15 second timeout per document. Raw text fallback on failure. Uses llama-3.3-70b-versatile.

---

## AI STACK

### Groq API

| Item | Value |
|------|-------|
| Model | llama-3.3-70b-versatile (ALL calls across all three tabs) |
| Tier | Free (no credit card) |
| Daily limit | 14,400 requests shared across all users |
| Key in code | `src/services/ai_classifier.py` → `_GROQ_API_KEY` |
| Key backup | `C:\Projects\Groq API key.txt` |
| Classification timeout | 8 seconds |
| PII detection timeout | 10 seconds |
| Extraction timeout | 15 seconds |
| Matter details timeout | 8 seconds |
| Fallback | All calls try/except, silent fallback always |

**Never change the model back to llama-3.1-8b-instant.**
All 7 references across 6 files use llama-3.3-70b-versatile.

### Four Corrections Learning Loops

**Loop 1 — Document Renaming**
- File: `%LOCALAPPDATA%\ClaimFileRenamer\corrections.json`
- GitHub: `corrections_[COMPUTERNAME].json` on corrections-sync branch
- Trigger: staff corrects WHO / ENTITY / WHAT / Duplicate in Tab 1
- Effect: exact filename match returns confidence 100, skips all inference

**Loop 2 — Privacy Redaction**
- File: `%LOCALAPPDATA%\ClaimFileRenamer\redaction_corrections.json`
- GitHub: `redaction_corrections_[COMPUTERNAME].json` on corrections-sync branch
- Trigger: staff erases AI box (should_not_redact) or draws manual box (should_redact)
- Effect: last 20 corrections included as few-shot examples in every AI Redact Groq call

**Loop 3 — Matter Details**
- File: `%LOCALAPPDATA%\ClaimFileRenamer\matter_corrections.json`
- GitHub: `matter_corrections_[COMPUTERNAME].json` on corrections-sync branch
- Trigger: staff manually corrects Client Name / Address / Date of Loss in Tab 3
- Effect: same bad extraction auto-corrected on any future document

**Loop 4 — GitHub Actions (automated build)**
- `build_installer.yml`: builds on code push, publishes GitHub Release
- `auto_harvest.yml`: triggers on corrections push, updates seed_examples.py
- AI-only releases: silent, staff never notified
- App update releases: status bar notification shown

### Corrections File Management
- Write lock (threading.Lock) on all corrections files — no corruption from concurrent writes
- Atomic write: write to .tmp then rename — no partial writes
- Corrupted file recovery: reader finds first valid JSON array boundary
- File size: not a concern at current scale, revisit at 500+ corrections per file

---

## KEY SOURCE FILES

```
C:\Projects\documentnamingapp\
├── main.py                              Entry point
├── build.spec                           PyInstaller config
├── requirements.txt                     Python dependencies
├── test_groq.py                         Quick Groq API test
├── harvest_corrections.py               Admin script
├── DOWNLOAD.md                          Staff download guidance
├── GITHUB_SYNC_SETUP.md                 Sync setup guide
├── .github/
│   └── workflows/
│       ├── auto_harvest.yml             LIVE — triggers on corrections push
│       └── build_installer.yml          LIVE — builds on code push
├── src/
│   ├── core/
│   │   ├── settings.py                  APP_VERSION lives here
│   │   └── models.py                    DocumentRecord — do not change
│   ├── services/
│   │   ├── ai_classifier.py             Groq classification — API KEY HERE
│   │   ├── ai_redactor.py               Groq PII second pass
│   │   ├── smart_extractor.py           Groq VP section extraction (70b)
│   │   ├── classifier.py                Rule-based WHO/ENTITY/WHAT
│   │   ├── date_engine.py               Date extraction
│   │   ├── normalizer.py                Filename normalisation
│   │   ├── confidence.py                Confidence scoring
│   │   ├── inference_pipeline.py        Orchestrator — corrections cache checked first
│   │   ├── corrections_store.py         Read/write corrections.json
│   │   ├── github_sync.py               GitHub API sync (urllib only)
│   │   ├── auto_harvest.py              Background harvest
│   │   ├── seed_examples.py             Baked-in examples (commit to update)
│   │   ├── redaction_corrections.py     Redaction corrections store + few-shot builder
│   │   ├── duplicate_detector.py        Duplicate detection
│   │   ├── rename_service.py            Safe rename with rollback
│   │   └── pdf_extractor.py             PyMuPDF text/image extraction
│   └── ui/
│       ├── main_window.py               Single QMainWindow, one QTabWidget
│       ├── privacy_tab.py               Tab 2 — visual PDF redaction
│       ├── extraction_tab.py            Tab 3 — verbatim pack generation
│       ├── table_model.py               Qt table model — Duplicate col now editable
│       ├── filter_proxy.py              Multi-criteria filter
│       ├── preview_widget.py            PDF preview
│       ├── worker.py                    Background thread
│       ├── settings_dialog.py           Settings + Corrections History
│       ├── history_dialog.py            Rename history
│       └── theme.py                     Dark theme
└── packaging/
    ├── installer.iss                    AppId and AppName locked
    ├── build_windows.bat                One-click local build
    └── version_info.txt                 Windows version resource
```

---

## LOCAL CORRECTIONS FILES

| File | Purpose |
|------|---------|
| `%LOCALAPPDATA%\ClaimFileRenamer\corrections.json` | Tab 1 renaming corrections |
| `%LOCALAPPDATA%\ClaimFileRenamer\learned_examples.json` | Harvested corrections from all machines |
| `%LOCALAPPDATA%\ClaimFileRenamer\redaction_corrections.json` | Tab 2 AI redaction corrections |
| `%LOCALAPPDATA%\ClaimFileRenamer\matter_corrections.json` | Tab 3 matter details corrections |

---

## KNOWN ENTITIES (classifier recognises these)

**Insurers (WHO = FF):**
Allianz, Suncorp, RACQ, QBE, IAG, NRMA, Budget Direct, Youi, Coles Insurance, Woolworths Insurance, RAA, SGIC, AAMI, GIO, Bingle, Shannons, Vero, Zurich, AIG, Chubb, CHU Insurance, Direct Insurance

**Builders / Engineers:**
AusCoast Builders, BMG Engineering, Sedgwick, Ezy Projects, EZ Projects, Campbell Constructions, Ambrose Construct Group, Kehoe Myers, Salt Water Roofing, Aizer Insurance Builders, InTouch Projects, Q-Tech Building Consultants, Live Electrical

**Solar / Specialist:**
PV Lab Australia, Solarez, Solarez Energy

**Weather:**
WeatherWatch, Early Warning Network, EWN, BoM

**ClaimsCo side:**
ClaimsCo, AusCoast, ACB, DOA, AAF

---

## SEED EXAMPLES (current set in seed_examples.py)

```
FF - 11.12.2025 - Allianz - IDR FDL.pdf
  → who=FF, entity=Allianz, what=IDR FDL

Complainant - 12.11.2025 - Solarez - Solar testing report.pdf
  → who=Complainant, entity=Solarez, what=Solar Testing Report

AFCA - 16.03.2026 - AFCA - Written Preliminary Assessment.pdf
  → who=AFCA, entity=AFCA, what=Written Preliminary Assessment

Complainant - 15.08.2025 - AusCoast - Variation Report.pdf
  → who=Complainant, entity=AusCoast Builders, what=Variation Report

FF - 06.05.2025 - Ezy Projects - Roof Report.pdf
  → who=FF, entity=Ezy Projects, what=Roof Report
```

---

## DEVELOPMENT RULES

1. Always read entire codebase before writing any code
2. Never change AppId or AppName in installer.iss
3. Never commit Groq API key or GitHub token to repo
4. Never modify original PDF files — only write _REDACTED copies
5. Never break Tab 1 Document Renamer existing functionality
6. Never change DocumentRecord model fields
7. Never add spaCy back — Groq handles name detection
8. Never change Groq model — always llama-3.3-70b-versatile across all tabs
9. All Groq calls: try/except, timeout, silent fallback
10. All GitHub sync calls: try/except, silent fail, never block UI
11. Corrections operations always async — never block UI
12. All corrections files: write lock + atomic write (write to .tmp then rename)
13. Run `python -m pytest tests/ -v` before every installer build
14. Commit and push to claimsco-documents-manager before building
15. Build installer to `C:\Projects\documentnamingapp\installer_output\`
16. If antivirus blocks: use `C:\Projects\installer_out\` and copy across
17. Update version in all three files before building
18. Distribute to staff via network share — never send GitHub Releases URL directly

---

## TEST COMMANDS

```bash
# Full test suite
python -m pytest tests/ -v

# Groq API test
python test_groq.py

# Corrections and sync test
python -c "
import sys; sys.path.insert(0,'.')
from src.services.corrections_store import CorrectionsStore
from src.services.github_sync import GitHubSync
print('Corrections OK:', CorrectionsStore().get_count() >= 0)
print('GitHub OK:', GitHubSync().is_available())
"

# Harvest (partially automated via GitHub Actions)
python harvest_corrections.py
```

---

## KNOWN ISSUES / WATCH LIST

| Issue | Status | Notes |
|-------|--------|-------|
| test_unsure_suffix failing | Accepted | Pre-existing, not blocking |
| Groq daily limit 14,400 | Monitor | Upgrade to Developer tier ~$10/month if needed |
| SmartScreen warning on GitHub download | By design | Distribute via network share only |
| Tab 3 date of loss extraction | Testing | Groq fallback added v2.1.2, confirm on real files |
| Corrections file size | Watch list | Not a problem now, revisit at 500+ corrections per file |
| Auto-learning loop 4-hour harvest | Planned | Currently daily, GitHub Actions upgrade pending |
| Close-event final sync push | Planned | Not yet built |
| Status bar update notification | Planned | For code changes only, not yet built |

---

## RELATED SYSTEMS

**AFCA Assistant v24** — Claude Project with system prompt, config JSON and knowledge pack. Receives the Verbatim Pack output from Tab 3 of this app.

**Matter Extraction GPT v5.1** — ChatGPT Custom GPT that reads matter PDFs and produces Master Evidence File and Verbatim Pack. Being partially replaced by Tab 3.

**ClaimGuard QLD Redaction Portal** — separate Streamlit app, redaction only, no AI, different project.
