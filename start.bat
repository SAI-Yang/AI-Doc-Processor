@echo off
cd /d "%~dp0"

:: Find Python
set PYTHON_CMD=
where python >nul 2>&1
if %errorlevel% equ 0 set PYTHON_CMD=python
if "%PYTHON_CMD%"=="" (
    where py >nul 2>&1
    if %errorlevel% equ 0 set PYTHON_CMD=py -3
)

if "%PYTHON_CMD%"=="" (
    echo Python not found. Install Python 3.10+ first.
    pause
    exit /b 1
)

start "" %PYTHON_CMD% -m app.main
exit
