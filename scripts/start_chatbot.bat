@echo off
echo ============================================================
echo CPG Conversational AI Chatbot
echo ============================================================
echo.

REM Change to project root (one level up from scripts/)
cd /d "%~dp0\.."

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found in PATH!
    echo.
    echo Please try one of these:
    echo   1. Run: py frontend\app_with_auth.py
    echo   2. Or in PowerShell: python frontend\app_with_auth.py
    echo   3. Or install Python and add to PATH
    echo.
    pause
    exit /b 1
)

echo Python found! Starting the web server...
echo.
echo Open your browser and go to: http://localhost:5000
echo.
echo Press Ctrl+C to stop the server
echo ============================================================
echo.

REM Try python, then py if that fails
python frontend\app_with_auth.py
if %errorlevel% neq 0 (
    echo.
    echo [WARN] 'python' command failed. Trying 'py' instead...
    py frontend\app_with_auth.py
)

echo.
pause
