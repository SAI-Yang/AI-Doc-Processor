"""应用入口 - 高 DPI 适配 + 启动主窗口"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from app.config import AppConfig
from app.font_manager import load_bundled_fonts, apply_font
from app.ui_main import MainWindow


def main():
    """应用入口"""
    try:
        # 高 DPI 适配
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    except Exception as e:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, f'启动失败：{e}\n请尝试重新安装或检查Python环境', '错误', 0)
        return

    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName('AI 文档批处理工具')
    app.setApplicationVersion('1.0.0')
    app.setOrganizationName('AIDocProcessor')

    # 加载配置（含字体偏好）
    config = AppConfig.load()
    bundled = load_bundled_fonts()

    # 确定字体：优先使用配置中保存的，其次打包字体，最后系统默认
    desired_family = config.font_family
    if desired_family and desired_family not in ('', 'Microsoft YaHei UI'):
        apply_font(app, desired_family, 10)
    else:
        for name, family in bundled.items():
            apply_font(app, family, 10)
            break
        else:
            font = QFont('Microsoft YaHei UI', 10)
            font.setStyleStrategy(QFont.PreferAntialias)
            app.setFont(font)

    # Qt-Material 浅色主题（必须在 QApplication 创建后导入）
    from qt_material import apply_stylesheet
    apply_stylesheet(app, theme='light_blue.xml')

    # 再次确保字体不被 qt-material 覆盖
    if desired_family and desired_family not in ('', 'Microsoft YaHei UI'):
        apply_font(app, desired_family, 10)
    else:
        for name, family in bundled.items():
            apply_font(app, family, 10)
            break
        else:
            app.setFont(font)

    # 覆盖 qt-material 中的中文显示问题
    font_family = desired_family
    if not font_family or font_family == 'Microsoft YaHei UI':
        font_family = 'Microsoft YaHei UI'
    app.setStyleSheet(app.styleSheet() + f"""
/* FONT_OVERRIDE_START */
QLabel, QLineEdit, QTextEdit, QPlainTextEdit, QStatusBar,
QComboBox, QListWidget, QTreeWidget {{
    font-family: "{font_family}", "Microsoft YaHei UI", "微软雅黑", sans-serif;
}}
QPushButton {{
    font-family: "{font_family}", "Microsoft YaHei UI", "微软雅黑", sans-serif;
    font-weight: 500;
}}
/* FONT_OVERRIDE_END */
""")

    # 创建并显示主窗口
    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
