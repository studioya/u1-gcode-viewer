@echo off
rem Adds "U1 Viewer" shortcuts to your Desktop and Start menu.
rem To remove them: python launcher\u1_viewer.pyw --uninstall
where python >nul 2>nul
if errorlevel 1 (
  echo Python wasn't found. Install it from https://www.python.org/downloads/ and run this again.
  pause
  exit /b 1
)
python "%~dp0launcher\u1_viewer.pyw" --install
