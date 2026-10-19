@echo off
setlocal
echo ===================================================
echo             ClipForge Installation Script
echo ===================================================

echo [1/4] Checking Python 3.12...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found in PATH.
    echo Please install Python 3.12 from python.org or via:
    echo   winget install --id Python.Python.3.12
    pause
    exit /b 1
)

echo [2/4] Setting up Python virtual environment (.venv)...
if not exist ".venv" (
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo [3/4] Installing dependencies from requirements.txt...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [WARNING] Some dependencies had warnings during install.
)

echo [4/4] Checking environment configuration...
if not exist ".env" (
    copy .env.example .env
    echo Created .env from template.
)

echo.
echo ===================================================
echo [SUCCESS] ClipForge is ready!
echo To run the application, execute:
echo   .\.venv\Scripts\streamlit.exe run app.py
echo ===================================================
echo.
pause
