@echo off
cd /d "%~dp0"
echo === JARVIS setup ===
echo.
py -3.11 --version
if errorlevel 1 (
  echo [ERROR] Python 3.11 not found. Install python-3.11.9-amd64.exe first.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  py -3.11 -m venv .venv
)
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Failed to create .venv
  pause
  exit /b 1
)
echo Installing packages. This takes 5-10 minutes...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo [ERROR] Package install failed. Send a screenshot of this window.
  pause
  exit /b 1
)
if not exist ".env" copy ".env.example" ".env" > nul
echo.
echo ===== SETUP COMPLETE =====
echo Next: open .env with Notepad, paste your API key, then run start_jarvis.bat
pause
