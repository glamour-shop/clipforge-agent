@echo off
if not exist ".venv\Scripts\streamlit.exe" (
    echo [INFO] Virtual environment not found. Running setup.bat first...
    call setup.bat
)
echo Starting ClipForge...
.\.venv\Scripts\streamlit.exe run app.py
pause
