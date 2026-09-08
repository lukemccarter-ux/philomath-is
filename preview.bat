@echo off
rem Validate now.json and gallery.json, build the self-contained previews, open the standalone one.
cd /d "%~dp0"
python build.py
if errorlevel 1 (
  echo.
  pause
  exit /b 1
)
start "" "dist\philomath-standalone.html"
