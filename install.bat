@echo off
chcp 65001 > nul
title AI 文档批处理工具 - 一键安装

echo ============================================
echo   AI 文档批处理工具 v1.1 - 安装程序
echo ============================================
echo.

:: 检查 Python
echo [1/4] 检测 Python 环境...
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo     [错误] 未检测到 Python
    echo     请先安装 Python 3.10+:
    echo     1. 打开 https://www.python.org/downloads/
    echo     2. 安装时勾选 "Add Python to PATH"
    echo     3. 重新运行本脚本
    echo.
    start https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set pyver=%%i
echo     Python %pyver% - 正常

:: 检查 pip
echo [2/4] 安装 Python 依赖...
python -m pip install --upgrade pip -q > nul 2>&1
python -m pip install -r requirements.txt -q
if %errorlevel% neq 0 (
    echo     尝试使用国内镜像...
    python -m pip install -r requirements.txt -q -i https://pypi.tuna.tsinghua.edu.cn/simple
    if %errorlevel% neq 0 (
        echo     [错误] 依赖安装失败
        echo     请检查网络连接后重试
        pause
        exit /b 1
    )
)
echo     依赖安装完成

:: 安装 PyQt5
echo [3/4] 安装 GUI 组件...
python -m pip install PyQt5 pyqtgraph -q
if %errorlevel% neq 0 (
    python -m pip install PyQt5 pyqtgraph -q -i https://pypi.tuna.tsinghua.edu.cn/simple
)
echo     GUI 组件安装完成

:: 下载字体（使用 PowerShell，兼容 Windows 7+）
echo [4/4] 下载字体文件...
if not exist fonts\ mkdir fonts
if not exist fonts\LXGWWenKai-Regular.ttf (
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest -Uri 'https://github.com/lxgw/LxgwWenKai/releases/download/v1.522/LXGWWenKai-Regular.ttf' -OutFile 'fonts\LXGWWenKai-Regular.ttf' -TimeoutSec 10 } catch { Write-Host 'skip' }}"
    if exist fonts\LXGWWenKai-Regular.ttf (
        echo     字体下载完成
    ) else (
        echo     字体下载跳过（不影响使用）
    )
)

echo.
echo ============================================
echo   安装完成！
echo ============================================
echo.
echo 启动方式：双击 start.bat
echo.
pause
