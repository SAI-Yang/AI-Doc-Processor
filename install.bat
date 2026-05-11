@echo off
title AI Doc Processor - Install

echo ============================================
echo   AI Doc Processor v1.1.2 Installer
echo ============================================
echo.

:: Check Python
echo [1/4] Checking Python...
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found. Please install Python 3.10+
    echo https://www.python.org/downloads/
    echo.
    start https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Get version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set pyver=%%i
echo    Python %pyver%

:: Upgrade pip
echo [2/4] Installing dependencies...
python -m pip install --upgrade pip -q > nul 2>&1

:: Install PyQt5 (biggest dep, do it first)
echo    Installing PyQt5 (may take a few minutes)...
pip install PyQt5 > nul 2>&1
if %errorlevel% neq 0 (
    echo    Retry with mirror...
    pip install PyQt5 -i https://pypi.tuna.tsinghua.edu.cn/simple > nul 2>&1
)

:: Install rest from requirements
pip install -r requirements.txt > nul 2>&1
if %errorlevel% neq 0 (
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple > nul 2>&1
)

echo    Dependencies installed

:: Download font
echo [3/4] Downloading font...
if not exist fonts\ mkdir fonts
if not exist fonts\LXGWWenKai-Regular.ttf (
    powershell -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;try{Invoke-WebRequest 'https://github.com/lxgw/LxgwWenKai/releases/download/v1.522/LXGWWenKai-Regular.ttf' -OutFile 'fonts\LXGWWenKai-Regular.ttf' -TimeoutSec 10}catch{}" > nul 2>&1
    if exist fonts\LXGWWenKai-Regular.ttf (
        echo    Font downloaded
    ) else (
        echo    Font skipped (not required)
    )
)

:: Verify
echo [4/4] Verifying...
python -c "from PyQt5.QtWidgets import QApplication; import sys; a=QApplication(sys.argv); print('OK')" > nul 2>&1
if %errorlevel% equ 0 (
    echo    PyQt5 OK
) else (
    echo    PyQt5 may not work correctly
)

echo.
echo ============================================
echo   Done! Run start.bat to launch
echo ============================================
echo.
pause
