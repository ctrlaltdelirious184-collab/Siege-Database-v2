@echo off
setlocal
cd /d "%~dp0"

:: 1. Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] ERROR: Python is not installed or not in your PATH.
    echo.
    echo Please install Python 3.10+ from: https://www.python.org/downloads/
    echo IMPORTANT: Make sure to check "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)

:: 2. Auto-install requirements (Silent)
echo [+] Initializing Siege Database v2...
python -m pip install -r requirements.txt --quiet --no-warn-script-location

:: 3. Launch App
echo [+] Launching...
start "" pythonw main.py
exit
