@echo off
REM Build script for Claim File Renamer on Windows 11
REM Prerequisites: Python 3.12+, pip, Inno Setup (optional for installer)

echo ============================================
echo  Claim File Renamer - Build Script
echo ============================================
echo.

REM Step 1: Create virtual environment
echo [1/4] Creating virtual environment...
python -m venv venv
call venv\Scripts\activate.bat

REM Step 2: Install dependencies
echo [2/4] Installing dependencies...
pip install -r requirements.txt

REM Step 3: Build with PyInstaller
echo [3/4] Building executable with PyInstaller...
pyinstaller build.spec --clean --noconfirm

echo.
echo ============================================
echo  Build complete!
echo  Output: dist\ClaimFileRenamer\
echo  Run:    dist\ClaimFileRenamer\ClaimFileRenamer.exe
echo ============================================
echo.

REM Step 4: Build installer (optional)
where iscc >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [4/4] Building installer with Inno Setup...
    iscc packaging\installer.iss
    echo.
    echo Installer created: installer_output\ClaimFileRenamer_Setup_1.0.0.exe
) else (
    echo [4/4] Inno Setup not found. Skipping installer creation.
    echo       Install Inno Setup from https://jrsoftware.org/isdl.php
    echo       Then run: iscc packaging\installer.iss
)

echo.
echo Done!
pause
