@echo off
cd /d "%~dp0"
echo AI Doc Processor Installer
echo ==========================
echo.

:: Find Python by trying commands directly
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
    echo.
    echo [ERROR] Python not found
    echo.
    echo This software requires Python 3.10 or higher.
    echo Download from: https://www.python.org/downloads/
    echo.
    echo When installing Python, make sure to check:
    echo   "Add Python to PATH"
    echo.
    start https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Using: %PY_CMD%
%PY_CMD% --version
echo.

:: Install dependencies
echo Installing dependencies...
%PY_CMD% -m pip install --upgrade pip -q
%PY_CMD% -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Retry with mirror...
    %PY_CMD% -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
)

%PY_CMD% -m pip install PyQt5
if %errorlevel% neq 0 (
    echo Retry PyQt5 with mirror...
    %PY_CMD% -m pip install PyQt5 -i https://pypi.tuna.tsinghua.edu.cn/simple
)

echo.
echo ===== INSTALL COMPLETE =====
echo Run start.bat to launch
pause
