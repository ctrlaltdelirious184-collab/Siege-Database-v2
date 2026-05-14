@echo off
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed or not in your PATH.
    echo Please install Python from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)
cd /d "%~dp0"
python main.py
if %errorlevel% neq 0 (
    echo.
    echo An error occurred. See above for details.
    pause
)
