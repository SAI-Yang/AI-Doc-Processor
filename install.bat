@echo off
cd /d "%~dp0"

echo AI Doc Processor Installer
echo ==========================
echo.

:: Try different Python commands
set PYTHON_CMD=
where python >nul 2>&1
if %errorlevel% equ 0 set PYTHON_CMD=python
if "%PYTHON_CMD%"=="" (
    where py >nul 2>&1
    if %errorlevel% equ 0 set PYTHON_CMD=py -3
)
if "%PYTHON_CMD%"=="" (
    where python3 >nul 2>&1
    if %errorlevel% equ 0 set PYTHON_CMD=python3
)

if "%PYTHON_CMD%"=="" (
    echo Python not found! Please install Python 3.10+
    echo https://www.python.org/downloads/
    start https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Using: %PYTHON_CMD%
echo.
echo Installing dependencies...

%PYTHON_CMD% -m pip install --upgrade pip -q
%PYTHON_CMD% -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    %PYTHON_CMD% -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
)

%PYTHON_CMD% -m pip install PyQt5
if %errorlevel% neq 0 (
    %PYTHON_CMD% -m pip install PyQt5 -i https://pypi.tuna.tsinghua.edu.cn/simple
)

echo.
echo Done! Run start.bat
pause
