@echo off
cd /d "%~dp0"

:: Find Python
set PY_CMD=
python --version >nul 2>&1
if %errorlevel% equ 0 set PY_CMD=python
if "%PY_CMD%"=="" (
    py -3 --version >nul 2>&1
    if %errorlevel% equ 0 set PY_CMD=py -3
)
if "%PY_CMD%"=="" (
    python3 --version >nul 2>&1
    if %errorlevel% equ 0 set PY_CMD=python3
)

if "%PY_CMD%"=="" (
    echo Python not found. Run install.bat first.
    pause
    exit /b 1
)

start "" %PY_CMD% -m app.main
exit
