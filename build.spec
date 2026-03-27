# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for ClaimsCo Document Tools v2.0.0

import sys
import os
import importlib

block_cipher = None

# ── Locate spaCy model ──────────────────────────────────────────────
_spacy_model_data = []
try:
    import en_core_web_sm
    model_dir = os.path.dirname(en_core_web_sm.__file__)
    _spacy_model_data.append((model_dir, 'en_core_web_sm'))
except ImportError:
    print("WARNING: en_core_web_sm not installed — Privacy Redaction NER will be disabled")

# ── Optional: bundle GitHub sync token and Groq key ──────────────────
_extra_datas = []
_token_path = 'C:/Projects/GitHub sync token.txt'
if os.path.exists(_token_path):
    _extra_datas.append((_token_path, '.'))
    print(f"Bundling GitHub sync token: {_token_path}")

_groq_key_path = 'C:/Projects/Groq API key.txt'
if os.path.exists(_groq_key_path):
    _extra_datas.append((_groq_key_path, '.'))
    print(f"Bundling Groq API key: {_groq_key_path}")

# Also bundle the .groq_key if present in src/services/
_groq_dotkey = 'src/services/.groq_key'
if os.path.exists(_groq_dotkey):
    _extra_datas.append((_groq_dotkey, 'src/services'))

a = Analysis(
    ['main.py'],   # entry point — the three-tab app
    pathex=[],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('src', 'src'),
    ] + _spacy_model_data + _extra_datas,
    hiddenimports=[
        # Qt
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtSvgWidgets',
        # PDF libraries
        'fitz',
        'pdfplumber',
        'pdfminer',
        'pdfminer.high_level',
        'pdfminer.layout',
        'pdfminer.pdfpage',
        'pdfminer.converter',
        'pdfminer.pdfinterp',
        # OCR / image
        'pytesseract',
        'pdf2image',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        # Word documents
        'docx',
        'docx.document',
        'docx.oxml',
        # Groq AI
        'groq',
        'httpx',
        'httpcore',
        'anyio',
        'sniffio',
        'h11',
        'pydantic',
        'pydantic_core',
        'annotated_types',
        # spaCy (full set for PyInstaller bundling)
        'spacy',
        'spacy.lang.en',
        'spacy.pipeline',
        'spacy.lexeme',
        'spacy.tokens',
        'en_core_web_sm',
        'thinc',
        'blis',
        'cymem',
        'murmurhash',
        'preshed',
        'srsly',
        'wasabi',
        'catalogue',
        'confection',
        'tqdm',
        # src package — all modules
        'src',
        'src.core',
        'src.core.settings',
        'src.core.models',
        'src.services',
        'src.services.classifier',
        'src.services.confidence',
        'src.services.date_engine',
        'src.services.duplicate_detector',
        'src.services.inference_pipeline',
        'src.services.normalizer',
        'src.services.pdf_extractor',
        'src.services.rename_service',
        'src.services.ai_classifier',
        'src.services.ai_redactor',
        'src.services.smart_extractor',
        'src.services.seed_examples',
        'src.services.corrections_store',
        'src.services.github_sync',
        'src.services.auto_harvest',
        'src.ui',
        'src.ui.filter_proxy',
        'src.ui.history_dialog',
        'src.ui.main_window',
        'src.ui.preview_widget',
        'src.ui.settings_dialog',
        'src.ui.table_model',
        'src.ui.theme',
        'src.ui.worker',
        'src.ui.privacy_tab',
        'src.ui.extraction_tab',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ClaimsCo_Tools',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico' if os.path.exists('assets/icon.ico') else None,
    version='packaging/version_info.txt',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ClaimsCo_Tools',
)
