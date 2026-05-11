@echo off
chcp 65001 > nul
title AI 文档批处理工具
echo 正在启动 AI 文档批处理工具...
cd /d "%~dp0"
python -m app.main
if %errorlevel% neq 0 (
    echo 启动失败，请先运行 install.bat 安装依赖
    pause
)
