@echo off

chcp 65001 > nul
color 0B
title CSFloat Helper - Launcher
cls

echo ╔════════════════════════════════════════════════════════════════════════════╗
echo ║                           CSFLOAT HELPER v2.0 by Gradinaz                  ║
echo ╚════════════════════════════════════════════════════════════════════════════╝
echo.

REM ============================================================================
REM Step 1: Check Python installation
REM ============================================================================
echo [1/4] Checking Python installation...

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [✗] Python is not installed!
    echo.
    echo Please download Python 3.10+ from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation!
    echo.
    timeout /t 5
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [✓] Python %PYTHON_VERSION% detected
echo.

REM ============================================================================
REM Step 2: Check pip
REM ============================================================================
echo [2/4] Checking pip...

python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [✗] pip is not installed!
    echo.
    echo Installing pip...
    python -m ensurepip --upgrade
    if %errorlevel% neq 0 (
        echo [✗] Failed to install pip
        timeout /t 5
        exit /b 1
    )
)

echo [✓] pip is available
echo.

REM ============================================================================
REM Step 3: Check and install dependencies
REM ============================================================================
echo [3/4] Checking dependencies...

if not exist "requirements.txt" (
    echo [!] requirements.txt not found, creating...
    (
        echo PyQt6^>=6.6.0
        echo requests^>=2.31.0
        echo pandas^>=2.0.0
        echo emoji^>=2.10.0
    ) > requirements.txt
    echo [✓] requirements.txt created
    echo.
)

REM Check critical dependencies
set MISSING_DEPS=0

python -c "import PyQt6" >nul 2>&1
if %errorlevel% neq 0 (
    echo [✗] PyQt6 is not installed
    set MISSING_DEPS=1
) else (
    echo [✓] PyQt6 is installed
)

python -c "import requests" >nul 2>&1
if %errorlevel% neq 0 (
    echo [✗] requests is not installed
    set MISSING_DEPS=1
) else (
    echo [✓] requests is installed
)

python -c "import pandas" >nul 2>&1
if %errorlevel% neq 0 (
    echo [✗] pandas is not installed
    set MISSING_DEPS=1
) else (
    echo [✓] pandas is installed
)

python -c "import emoji" >nul 2>&1
if %errorlevel% neq 0 (
    echo [✗] emoji is not installed
    set MISSING_DEPS=1
) else (
    echo [✓] emoji is installed
)

echo.

REM Install missing dependencies
if %MISSING_DEPS%==1 (
    echo [!] Installing missing dependencies...
    echo This may take 2-3 minutes...
    echo.
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo.
        echo [✗] Failed to install dependencies
        echo.
        echo Troubleshooting:
        echo 1. Make sure you have internet connection
        echo 2. Try running as Administrator
        echo 3. Check if antivirus is blocking pip
        echo.
        timeout /t 10
        exit /b 1
    )
    echo.
    echo [✓] All dependencies installed successfully!
    timeout /t 2 /nobreak >nul
)

REM ============================================================================
REM Step 4: Launch application
REM ============================================================================
echo [4/4] Launching CSFloat Helper...
timeout /t 1 /nobreak >nul

REM Clear screen and show header again
cls
echo ╔════════════════════════════════════════════════════════════════════════════╗
echo ║                           CSFLOAT HELPER v2.0 by Gradinaz                  ║
echo ╚════════════════════════════════════════════════════════════════════════════╝
echo.
echo.

REM Launch application in background without console window
start "" pythonw.exe csfloat_helper.py

REM Wait 10 seconds and close
timeout /t 10 /nobreak >nul

REM Exit the batch file
exit
