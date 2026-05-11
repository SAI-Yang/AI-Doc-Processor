#!/usr/bin/env python3
"""PyInstaller 打包脚本

用法:
    python build.py            # 单文件模式
    python build.py --dir      # 目录模式
    python build.py --clean    # 清理构建产物
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
APP_NAME = 'AI文档批处理工具'


def build_onefile():
    """单文件模式打包"""
    print('==> 单文件模式打包...')

    cmd = [
        'pyinstaller',
        '--onefile',              # 单文件
        '--windowed',             # 无控制台窗口（Windows GUI）
        '--name', APP_NAME,
        '--noconfirm',            # 覆盖输出目录
        '--clean',
        # 添加数据文件
        '--add-data', f'{PROJECT_ROOT / "app"}{os.pathsep}app',
        # 隐藏导入
        '--hidden-import', 'PyQt5.sip',
        '--hidden-import', 'app.config',
        '--hidden-import', 'app.document',
        '--hidden-import', 'app.llm_client',
        '--hidden-import', 'app.template_manager',
    ]

    # 图标（如果存在）
    icon_path = PROJECT_ROOT / 'app_icon.ico'
    if icon_path.exists():
        cmd.extend(['--icon', str(icon_path)])

    cmd.append(str(PROJECT_ROOT / 'app' / 'main.py'))

    subprocess.check_call(cmd)
    print(f'==> 打包完成! 可执行文件在 dist/{APP_NAME}.exe')


def build_dir():
    """目录模式打包"""
    print('==> 目录模式打包...')

    cmd = [
        'pyinstaller',
        '--onedir',               # 目录模式
        '--windowed',
        '--name', APP_NAME,
        '--noconfirm',
        '--clean',
        '--add-data', f'{PROJECT_ROOT / "app"}{os.pathsep}app',
        '--hidden-import', 'PyQt5.sip',
        '--hidden-import', 'app.config',
        '--hidden-import', 'app.document',
        '--hidden-import', 'app.llm_client',
        '--hidden-import', 'app.template_manager',
    ]

    icon_path = PROJECT_ROOT / 'app_icon.ico'
    if icon_path.exists():
        cmd.extend(['--icon', str(icon_path)])

    cmd.append(str(PROJECT_ROOT / 'app' / 'main.py'))

    subprocess.check_call(cmd)
    print(f'==> 打包完成! 目录在 dist/{APP_NAME}/')


def clean():
    """清理构建产物"""
    dirs_to_remove = ['build', 'dist']
    files_to_remove = list(Path(PROJECT_ROOT).glob('*.spec'))

    for d in dirs_to_remove:
        path = PROJECT_ROOT / d
        if path.exists():
            shutil.rmtree(path)
            print(f'  已删除: {path}')

    for f in files_to_remove:
        if f.exists():
            f.unlink()
            print(f'  已删除: {f}')

    print('==> 清理完成')


def main():
    if '--clean' in sys.argv:
        clean()
        return

    if '--dir' in sys.argv:
        build_dir()
    else:
        build_onefile()


if __name__ == '__main__':
    main()
