@echo off
rem Import everything waiting in the Drive-synced inbox, then commit and push.
rem Dry run first so you can see what will happen; press a key to apply.
setlocal
set "INBOX=%USERPROFILE%\Desktop\OpenRouter Inbox\Personal Queue\philomath_resources"
cd /d "%~dp0"
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
