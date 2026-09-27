@echo off
rem Import everything waiting in the Drive-synced inbox, then commit and push.
rem Dry run first so you can see what will happen; press a key to apply.
setlocal
set "INBOX=%USERPROFILE%\Desktop\OpenRouter Inbox\Personal Queue\philomath_resources"
cd /d "%~dp0"
echo.
echo === Sync with GitHub first (two working copies exist: laptop12 and musicbox) ===
git pull --ff-only origin main
if errorlevel 1 (
  echo This copy has diverged from GitHub. Run "git pull" by hand and resolve before importing.
  goto end
)
echo.
echo === Dry run ===
python tools\import_media.py "%INBOX%"
if errorlevel 1 goto end
echo.
set /p GO=Apply, commit and push? [y/N]
if /i not "%GO%"=="y" goto end
python tools\import_media.py "%INBOX%" --write --push
:end
echo.
pause
