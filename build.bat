@echo off
REM ============================================================
REM  BI Report Assistant — Build Script
REM  Produces: installer_output\BI-Report-Assistant-Setup-1.0.0.exe
REM ============================================================

setlocal

echo.
echo ========================================
echo  BI Report Assistant Build
echo ========================================
echo.

REM ── Check Python ─────────────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found on PATH. Install Python 3.10+ and try again.
    pause & exit /b 1
)

REM ── Check PyInstaller ────────────────────────────────────────────────────────
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM ── Check Inno Setup ─────────────────────────────────────────────────────────
set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
    set ISCC="%ProgramFiles%\Inno Setup 6\ISCC.exe"
)
if not exist %ISCC% (
    echo WARNING: Inno Setup not found. Will build the .exe bundle but skip installer creation.
    echo          Download Inno Setup from https://jrsoftware.org/isinfo.php
    set SKIP_INSTALLER=1
) else (
    set SKIP_INSTALLER=0
)

REM ── Install dependencies ─────────────────────────────────────────────────────
echo Installing Python dependencies...
pip install -r requirements-local.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause & exit /b 1
)

REM ── Clean previous build ─────────────────────────────────────────────────────
echo Cleaning previous build...
if exist dist\bi_report_assistant rmdir /s /q dist\bi_report_assistant
if exist build\bi_report_assistant rmdir /s /q build\bi_report_assistant

REM ── PyInstaller ──────────────────────────────────────────────────────────────
echo.
echo Running PyInstaller...
echo.
python -m PyInstaller bi_report_assistant.spec --clean --noconfirm
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause & exit /b 1
)
echo.
echo PyInstaller build complete: dist\bi_report_assistant\
echo.

REM ── Inno Setup ───────────────────────────────────────────────────────────────
if "%SKIP_INSTALLER%"=="1" goto :done

echo Running Inno Setup...
if not exist installer_output mkdir installer_output
%ISCC% bi_report_assistant.iss
if errorlevel 1 (
    echo ERROR: Inno Setup build failed.
    pause & exit /b 1
)
echo.
echo Installer created in installer_output\
echo.

:done
echo ========================================
echo  Build complete!
echo ========================================
echo.
if "%SKIP_INSTALLER%"=="0" (
    echo Installer: installer_output\BI-Report-Assistant-Setup-1.0.0.exe
) else (
    echo Bundle:    dist\bi_report_assistant\bi_report_assistant.exe
    echo           ^(Install Inno Setup to create a proper installer^)
)
echo.
pause
