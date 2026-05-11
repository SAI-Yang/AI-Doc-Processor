@echo off
chcp 65001 > nul
title AI 文档批处理工具 - 一键安装

echo ============================================
echo   AI 文档批处理工具 v1.0 - 安装程序
echo ============================================
echo.

:: 检查 Python
echo [1/5] 检测 Python 环境...
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo     未检测到 Python，正在打开下载页面...
    start https://www.python.org/downloads/
    echo     请安装 Python 3.10+ 后重新运行本脚本
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set pyver=%%i
echo     Python %pyver% ✓

:: 安装依赖
echo [2/5] 安装 Python 依赖...
python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt -q
if %errorlevel% neq 0 (
    echo    安装失败，尝试使用国内镜像...
    python -m pip install -r requirements.txt -q -i https://pypi.tuna.tsinghua.edu.cn/simple
)
echo     依赖安装完成 ✓

:: 安装可选依赖（DOCX/PDF支持）
echo [3/5] 安装可选依赖...
python -m pip install python-docx pdfplumber PyPDF2 -q
echo     可选依赖安装完成 ✓

:: 安装 PyQt5（GUI 必需）
echo [4/5] 安装 GUI 依赖...
python -m pip install PyQt5 pyqtgraph -q
if %errorlevel% neq 0 (
    echo    安装失败，尝试使用国内镜像...
    python -m pip install PyQt5 pyqtgraph -q -i https://pypi.tuna.tsinghua.edu.cn/simple
)
echo     GUI 依赖安装完成 ✓

:: 下载字体
echo [5/5] 下载字体文件...
if not exist fonts\ (
    mkdir fonts
)
if not exist fonts\LXGWWenKai-Regular.ttf (
    echo     下载霞鹜文楷字体...
    curl -sL -o fonts\LXGWWenKai-Regular.ttf ^
        "https://github.com/lxgw/LxgwWenKai/releases/download/v1.522/LXGWWenKai-Regular.ttf" ^
        --connect-timeout 10
    if exist fonts\LXGWWenKai-Regular.ttf (
        echo     字体下载完成 ✓
    ) else (
        echo     字体下载失败（可跳过，不影响运行）
    )
)

echo.
echo ============================================
echo   安装完成！
echo ============================================
echo.
echo 启动方式：
echo   双击运行 start.bat 或：
echo   python -m app.main
echo.
pause
