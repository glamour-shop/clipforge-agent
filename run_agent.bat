@echo off
title ClipForge Autonomous Daily Shorts Agent
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" agent.py --daemon --interval 60
) else (
    python agent.py --daemon --interval 60
)
pause
