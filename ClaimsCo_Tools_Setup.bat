@echo off
setlocal

echo ================================================================
echo  ClaimsCo Document Tools — One-Click Setup
echo ================================================================
echo.

:: ── 1. Check Python is installed ─────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not on your PATH.
    echo.
    echo Download Python 3.11+ from:
    echo   https://www.python.org/downloads/
    echo.
    echo Make sure to tick "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo Python found:
python --version
echo.

:: ── 2. Install pip dependencies ───────────────────────────────────────────────
echo Installing Python dependencies...
echo.
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR: pip install failed. Check the error messages above.
    pause
    exit /b 1
)

echo.
echo All Python packages installed successfully.
echo.

:: ── 3. Tesseract OCR ─────────────────────────────────────────────────────────
echo ================================================================
echo  Optional: Tesseract OCR  (required only for scanned/image PDFs)
echo ================================================================
echo.
echo If your PDFs contain scanned pages (images, not text), you need
echo Tesseract OCR. Text-based PDFs work without it.
echo.
echo Download Tesseract for Windows from:
echo   https://github.com/UB-Mannheim/tesseract/wiki
echo.
echo Install to the default location:
echo   C:\Program Files\Tesseract-OCR\tesseract.exe
echo.
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
    echo STATUS: Tesseract is already installed.
) else (
    echo STATUS: Tesseract is NOT installed.
)
echo.

:: ── 4. Poppler ────────────────────────────────────────────────────────────────
echo ================================================================
echo  Optional: Poppler  (required only if using Tesseract OCR)
echo ================================================================
echo.
echo Poppler converts PDF pages to images for OCR processing.
echo Download from:
echo   https://github.com/oschwartz10612/poppler-windows/releases
echo.
echo Extract to: C:\poppler\
echo (so the bin folder is at: C:\poppler\Library\bin)
echo.
if exist "C:\poppler\Library\bin\pdftoppm.exe" (
    echo STATUS: Poppler is already installed.
) else (
    echo STATUS: Poppler is NOT installed.
)
echo.

:: ── 5. Done ───────────────────────────────────────────────────────────────────
echo ================================================================
echo  Setup complete!
echo ================================================================
echo.
echo To launch the app, double-click ClaimsCo_Tools.py
echo (or run: python ClaimsCo_Tools.py)
echo.
pause
endlocal
