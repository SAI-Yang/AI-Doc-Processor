@echo off
cd /d "%~dp0"
python -m app.main
if %errorlevel% neq 0 (
    echo Launch failed. Run install.bat first.
    pause
)
