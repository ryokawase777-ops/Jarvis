@echo off
cd /d "%~dp0"
title JARVIS
set PYTHONUTF8=1
chcp 65001 > nul
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Run setup.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" main.py
pause
