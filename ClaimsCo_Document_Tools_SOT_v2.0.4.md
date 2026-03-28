# ClaimsCo Document Tools — Source of Truth
**Last updated:** 28 March 2026  
**Current version:** v2.0.4  
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
| 2.0.4 | **Current** | spaCy removed entirely, Groq PII detection, send-to-tab file passing fixed, installer 73MB (down from 98MB) |

### What is in v2.0.4
- spaCy completely removed — 0 references remain in codebase
- Groq handles all name/PII detection in Privacy Redaction tab
- `_detect_pii_with_groq()` method in privacy_tab.py
- `send_to_extraction` signal wired correctly between tabs
- `load_files()` implemented on both Privacy Redaction and Extraction tabs
- Pass buttons always visible, greyed out until files loaded
- Installer size: 73MB (spaCy model no longer bundled)
- Tests: 64/65 passing (1 pre-existing failure: test_unsure_suffix)
- Committed: 110cb68 on claimsco-documents-manager

---

## NEXT BUILD: Automated Learning Loop (not yet built)

The following changes are planned for the next session:

1. **Pull improvements on every open** — change harvest from once-per-day to every 4 hours
2. **Push corrections on app close** — closeEvent final sync (5 second max, never blocks)
3. **GitHub Actions: auto_harvest.yml** — triggers on corrections push, updates seed_examples.py automatically
4. **GitHub Actions: build_installer.yml** — builds installer on Windows runner, publishes GitHub Release
5. **Fixed download URL** — staff bookmark once, always get latest
6. **Update notification** — status bar shows "App update vX.X.X available" only for code changes, never for AI-only updates
7. **DOWNLOAD.md** — clear guidance on when to download vs when not to

Key distinction for notifications:
- AI improvement releases (seed_examples.py only) → silent, existing staff never notified
- App update releases (code changed) → status bar notification shown

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

---

## THREE-TAB ARCHITECTURE

### Tab 1 — Document Renamer

Already working well. Do not break it.

**Filename convention:**
```
[WHO] - [DD.MM.YYYY] - [ENTITY] - [WHAT].pdf
```

**WHO values:** Complainant, FF, AFCA, Unknown

**WHAT values:** Roof Report, IDR FDL, Quote, Scope of Repairs, Building Report, Supplementary Report, Letter of Engagement, Certificate of Insurance, PDS, AFCA Submission, Notice of Response, Photo Schedule, Solar Report, Solar Testing Report, Engineering Report, Scope of Works, Invoice, Agent Authority Form, Decline Letter, Desktop Assessment, Re-inspection Report, Policy Schedule, Claim Lodgement Email, Written Preliminary Assessment, Request for Information, Progress Report, Hail Report, Weather Report, Variation Report, Delegation of Authority

**Classification pipeline:**
1. Extract entity from filename third segment (confidence 0.90)
2. Rule-based classifier (date_engine.py, classifier.py, normalizer.py)
3. If confidence < 0.85: call Groq API
4. Check corrections.json before Groq call — exact filename or entity segment match returns immediately

**Send button:** "Send to Privacy Redaction →" always visible, greyed out until files loaded, enabled as soon as files load

### Tab 2 — Privacy Redaction

Visual PDF redaction. Pages rendered at 150 DPI using PyMuPDF.

**spaCy has been permanently removed. Do not re-add it.**
Groq handles all name/PII detection.

**Auto Redact — two passes:**

Pass 1 — Regex (always works offline):
- Phones: `(\+?61[\s-]?)?(0\d[\s-]?)[\d\s-]{8,10}`
- Policy numbers: `[A-Z]{2,4}[-]?\d{6,12}`
- Full addresses: digits + street + suburb + STATE + postcode
- Street numbers including alphanumeric (17A, Unit 3, Lot 5)
- Label-value pairs: Name:, Address:, Client:, Insured:, etc.
- Reference numbers near labels: Job Number:, Claim No:, etc.

Pass 2 — Groq (silent fail if unavailable):
- Sends first 3000 chars of page text
- Returns list of PII strings
- Merged and deduplicated with Pass 1

**Redaction state:** `dict[filepath: list[RedactionBox]]`, preserved when switching files

**Export:** `page.add_redact_annot()` + `doc.apply_redactions()` removes underlying text. Saves as `[name]_REDACTED.pdf`. Never modifies originals.

**Send button:** "Send to Claude Extraction Pack →" always visible, passes file paths to Tab 3

### Tab 3 — Claude Extraction Pack

Generates structured Verbatim Pack for Claude AFCA Assistant v24.

**Inputs:** PDFs + Matter Ref + Date of Loss

**VP sections:**
- VP1: PDS quotable clauses
- VP2: Complainant expert report conclusions/methodology
- VP3: FF expert reports and decision letters
- VP4: Scopes of works and quotes (both sides)
- VP5: Weather evidence
- VP6: Solar and specialist reports

**SmartExtractor routing:** classifies each doc then routes to correct extraction method. 15 second timeout per document. Raw text fallback on failure.

---

## AI STACK

### Groq API

| Item | Value |
|------|-------|
| Model | llama-3.1-8b-instant |
| Tier | Free (no credit card) |
| Daily limit | 14,400 requests shared across all users |
| Key in code | `src/services/ai_classifier.py` → `_GROQ_API_KEY` |
| Key backup | `C:\Projects\Groq API key.txt` |
| Classification timeout | 8 seconds |
| PII detection timeout | 10 seconds |
| Extraction timeout | 15 seconds |
| Fallback | All calls try/except, silent fallback always |

### Corrections Learning Loop

**Current state (partially manual):**

1. Staff corrects a field → `corrections.json` written locally
2. App pushes `corrections_[COMPUTERNAME].json` to `corrections-sync` branch on GitHub
3. Same session: corrections.json checked before Groq call
4. Daily on startup: auto-harvester pulls all machines' corrections, merges into `learned_examples.json`
5. Nick runs `harvest_corrections.py` monthly → updates `seed_examples.py` → commits → rebuilds installer

**Planned (next build — full automation):**
- Every 4-hour check instead of daily
- Final sync push on app close
- GitHub Actions auto-harvest and rebuild
- No manual steps by Nick ever

**Key files:**
- `src/services/corrections_store.py` — read/write corrections.json
- `src/services/github_sync.py` — GitHub API (urllib only, no extra pip deps)
- `src/services/auto_harvest.py` — background harvest
- `src/services/seed_examples.py` — baked-in examples (commit to update)
- `harvest_corrections.py` — admin script (currently manual)
- `%LOCALAPPDATA%\ClaimFileRenamer\corrections.json` — local corrections
- `%LOCALAPPDATA%\ClaimFileRenamer\learned_examples.json` — harvested examples

---

## KEY SOURCE FILES

```
C:\Projects\documentnamingapp\
├── main.py                          Entry point
├── build.spec                       PyInstaller config
├── requirements.txt                 Python dependencies
├── test_groq.py                     Quick Groq API test
├── harvest_corrections.py           Admin script
├── setup_github_secrets.py          (planned — not yet built)
├── DOWNLOAD.md                      (planned — not yet built)
├── GITHUB_SYNC_SETUP.md             Sync setup guide
├── .github/
│   └── workflows/
│       ├── auto_harvest.yml         (planned — not yet built)
│       └── build_installer.yml      (planned — not yet built)
├── src/
│   ├── core/
│   │   ├── settings.py              APP_VERSION lives here
│   │   └── models.py                DocumentRecord — do not change
│   ├── services/
│   │   ├── ai_classifier.py         Groq classification — API KEY HERE
│   │   ├── ai_redactor.py           Groq PII second pass
│   │   ├── smart_extractor.py       Groq VP section extraction
│   │   ├── classifier.py            Rule-based WHO/ENTITY/WHAT
│   │   ├── date_engine.py           Date extraction
│   │   ├── normalizer.py            Filename normalisation
│   │   ├── confidence.py            Confidence scoring
│   │   ├── inference_pipeline.py    Orchestrator
│   │   ├── corrections_store.py     Corrections JSON store
│   │   ├── github_sync.py           GitHub API sync
│   │   ├── auto_harvest.py          Background harvest
│   │   ├── seed_examples.py         Baked-in examples
│   │   ├── duplicate_detector.py    Duplicate detection
│   │   ├── rename_service.py        Safe rename with rollback
│   │   └── pdf_extractor.py         PyMuPDF text/image extraction
│   └── ui/
│       ├── main_window.py           Single QMainWindow, one QTabWidget
│       ├── privacy_tab.py           Tab 2 — visual PDF redaction
│       ├── extraction_tab.py        Tab 3 — verbatim pack generation
│       ├── table_model.py           Qt table model
│       ├── filter_proxy.py          Multi-criteria filter
│       ├── preview_widget.py        PDF preview
│       ├── worker.py                Background thread
│       ├── settings_dialog.py       Settings + Corrections History
│       ├── history_dialog.py        Rename history
│       └── theme.py                 Dark theme
└── packaging/
    ├── installer.iss                AppId and AppName locked
    ├── build_windows.bat            One-click build
    └── version_info.txt             Windows version resource
```

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
8. All Groq calls: try/except, timeout, silent fallback
9. All GitHub sync calls: try/except, silent fail, never block UI
10. Corrections operations always async — never block UI
11. Run `python -m pytest tests/ -v` before every installer build
12. Commit and push to claimsco-documents-manager before building
13. Build installer to `C:\Projects\documentnamingapp\installer_output\`
14. If antivirus blocks: use `C:\Projects\installer_out\` and copy across
15. Update version in all three files before building

---

## TEST COMMANDS

```bash
# Full test suite
python -m pytest tests/ -v

# Groq API test (both must PASS)
python test_groq.py

# Corrections and sync test
python -c "
import sys; sys.path.insert(0,'.')
from src.services.corrections_store import CorrectionsStore
from src.services.github_sync import GitHubSync
print('Corrections OK:', CorrectionsStore().get_count() >= 0)
print('GitHub OK:', GitHubSync().is_available())
"

# Harvest (currently manual — being automated)
python harvest_corrections.py
```

---

## KNOWN ISSUES / WATCH LIST

| Issue | Status | Notes |
|-------|--------|-------|
| test_unsure_suffix failing | Accepted | Pre-existing, not blocking |
| Groq daily limit 14,400 | Monitor | Upgrade to Developer tier if needed ~$10/month |
| Auto-learning loop manual | Next build | GitHub Actions automation planned |
| Antivirus blocking installer_output | Workaround | Build to installer_out and copy |

---

## RELATED SYSTEMS

**AFCA Assistant v24** — Claude Project with system prompt, config JSON and knowledge pack. Receives the Verbatim Pack output from Tab 3 of this app.

**Matter Extraction GPT v5.1** — ChatGPT Custom GPT that reads matter PDFs and produces Master Evidence File and Verbatim Pack. Being partially replaced by Tab 3.

**ClaimGuard QLD Redaction Portal** — separate Streamlit app, redaction only, no AI, different project.
