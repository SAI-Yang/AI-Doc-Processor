"""应用入口 - 高 DPI 适配 + 启动主窗口"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from app.ui_main import MainWindow


def main():
    """应用入口"""

    # 高 DPI 适配
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName('AI 文档批处理工具')
    app.setApplicationVersion('1.0.0')
    app.setOrganizationName('AIDocProcessor')

    # 全局字体
    font = QFont('Microsoft YaHei', 10)
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)

    # 创建并显示主窗口
    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
