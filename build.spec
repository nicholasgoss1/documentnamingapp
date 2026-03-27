# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for ClaimsCo Document Tools

import sys
import os

block_cipher = None

a = Analysis(
    ['ClaimsCo_Tools.py'],   # entry point — the combined 3-tab app
    pathex=[],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('src', 'src'),
    ],
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
        # src package
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
        'src.ui',
        'src.ui.filter_proxy',
        'src.ui.history_dialog',
        'src.ui.main_window',
        'src.ui.preview_widget',
        'src.ui.settings_dialog',
        'src.ui.table_model',
        'src.ui.theme',
        'src.ui.worker',
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
