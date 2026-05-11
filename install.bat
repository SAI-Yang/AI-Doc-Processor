@echo off
chcp 65001 > nul
title AI 文档批处理工具 - 一键安装

echo ============================================
echo   AI 文档批处理工具 v1.1 - 安装程序
echo ============================================
echo.

:: 检查 Python
echo [1/4] 检查 Python 环境...
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo   [错误] 未检测到 Python
    echo   请先安装 Python 3.10 或更高版本
    echo   下载地址: https://www.python.org/downloads/
    echo   安装时务必勾选 "Add Python to PATH"
    echo.
    start https://www.python.org/downloads/
    pause
    exit /b 1
)
python --version 2>&1
echo.

:: 升级 pip
echo [2/4] 升级 pip 并安装依赖...
python -m pip install --upgrade pip -q > nul 2>&1

:: 逐个安装依赖（方便定位哪个包失败）
echo   正在安装 PyQt5（可能需要几分钟，请耐心等待）...
pip install PyQt5 -q > nul 2>&1
if %errorlevel% neq 0 (
    echo   安装 PyQt5 失败，尝试清华镜像...
    pip install PyQt5 -q -i https://pypi.tuna.tsinghua.edu.cn/simple
)

echo   正在安装其余依赖...
pip install -r requirements.txt -q > nul 2>&1
if %errorlevel% neq 0 (
    echo   安装失败，尝试使用国内镜像...
    pip install -r requirements.txt -q -i https://pypi.tuna.tsinghua.edu.cn/simple
    if %errorlevel% neq 0 (
        echo.
        echo   [错误] 依赖安装失败
        echo   请检查网络连接后重新运行
        pause
        exit /b 1
    )
)
echo.

:: 下载字体
echo [3/4] 下载字体文件...
if not exist fonts\ mkdir fonts
if not exist fonts\LXGWWenKai-Regular.ttf (
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest -Uri 'https://github.com/lxgw/LxgwWenKai/releases/download/v1.522/LXGWWenKai-Regular.ttf' -OutFile 'fonts\LXGWWenKai-Regular.ttf' -TimeoutSec 10 } catch {} }" > nul 2>&1
    if exist fonts\LXGWWenKai-Regular.ttf (
        echo   字体下载完成
    ) else (
        echo   字体跳过（不影响运行）
    )
)
echo.

:: 完成
echo [4/4] 验证安装...
python -c "from PyQt5.QtWidgets import QApplication; print('  PyQt5 OK')" 2> nul
if %errorlevel% equ 0 (
    echo.
    echo ============================================
    echo   安装成功！可以启动应用了
    echo ============================================
    echo.
    echo 启动方式：双击 start.bat
    echo.
) else (
    echo.
    echo   [警告] PyQt5 可能未正确安装
    echo   请尝试手动运行: pip install PyQt5
)
pause
