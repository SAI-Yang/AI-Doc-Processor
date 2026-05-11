"""主窗口 - 整合所有组件"""

from pathlib import Path

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTabWidget, QToolBar, QAction,
    QStatusBar, QProgressBar, QLabel, QMessageBox,
    QFileDialog, QApplication, QMenu,
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QKeySequence, QIcon, QPixmap, QPainter, QColor

from app import (
    APP_NAME, APP_VERSION, SUPPORTED_EXTENSIONS,
    FILE_PENDING, FILE_PROCESSING, FILE_DONE, FILE_FAILED,
)
from app.config import AppConfig
from app.document import read_document
from app.ui_filelist import FileListWidget
from app.ui_template_panel import TemplatePanel
from app.ui_preview import PreviewWidget
from app.ui_batch import BatchControlWidget, LogWidget
from app.ui_settings import SettingsDialog
from app.ui_history import HistoryWidget


# ── 深色主题样式表 ──────────────────────────────────────

DARK_STYLESHEET = """
/* 全局 */
QMainWindow, QWidget {
    background-color: #0d1117;
    color: #e6edf3;
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
}

/* 菜单栏 */
QMenuBar {
    background-color: #161b22;
    color: #e6edf3;
    border-bottom: 1px solid #30363d;
    padding: 2px 0;
}
QMenuBar::item {
    padding: 6px 12px;
    background: transparent;
}
QMenuBar::item:selected {
    background-color: #1f6feb;
}
QMenu {
    background-color: #161b22;
    color: #e6edf3;
    border: 1px solid #30363d;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #1f6feb;
}
QMenu::separator {
    height: 1px;
    background: #30363d;
    margin: 4px 8px;
}

/* 工具栏 */
QToolBar {
    background-color: #161b22;
    border-bottom: 1px solid #30363d;
    padding: 4px 8px;
    spacing: 6px;
}
QToolBar QToolButton {
    background-color: #21262d;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 13px;
    min-height: 28px;
}
QToolBar QToolButton:hover {
    background-color: #30363d;
    border-color: #8b949e;
}
QToolBar QToolButton:pressed {
    background-color: #1f6feb;
}
QToolBar QToolButton:disabled {
    color: #484f58;
    background-color: #161b22;
    border-color: #21262d;
}

/* 状态栏 */
QStatusBar {
    background-color: #161b22;
    color: #8b949e;
    border-top: 1px solid #30363d;
    font-size: 12px;
}
QStatusBar::item {
    border: none;
}

/* 进度条 */
QProgressBar {
    background-color: #21262d;
    border: 1px solid #30363d;
    border-radius: 4px;
    text-align: center;
    color: #e6edf3;
    font-size: 12px;
    min-height: 18px;
}
QProgressBar::chunk {
    background-color: #1f6feb;
    border-radius: 3px;
}

/* 标签页 */
QTabWidget::pane {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-top: none;
    border-radius: 0 0 6px 6px;
}
QTabBar::tab {
    background-color: #161b22;
    color: #8b949e;
    border: 1px solid #30363d;
    border-bottom: none;
    padding: 8px 20px;
    margin-right: 2px;
    border-radius: 6px 6px 0 0;
    font-size: 13px;
}
QTabBar::tab:selected {
    background-color: #0d1117;
    color: #e6edf3;
    border-bottom-color: #0d1117;
}
QTabBar::tab:hover:!selected {
    color: #e6edf3;
}

/* 列表 */
QListWidget {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    color: #e6edf3;
    outline: none;
    font-size: 12px;
}
QListWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid #21262d;
    border-radius: 4px;
}
QListWidget::item:selected {
    background-color: #1f6feb22;
    border-left: 3px solid #1f6feb;
}
QListWidget::item:hover:!selected {
    background-color: #1c2128;
}

/* 编辑框 */
QTextEdit, QPlainTextEdit {
    background-color: #0d1117;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 4px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 13px;
    padding: 6px;
    selection-background-color: #1f6feb;
}

/* 输入框 */
QLineEdit {
    background-color: #0d1117;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 13px;
}
QLineEdit:focus {
    border-color: #1f6feb;
}

/* 下拉框 */
QComboBox {
    background-color: #21262d;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 4px;
    padding: 5px 10px;
    font-size: 13px;
    min-height: 24px;
}
QComboBox:hover {
    border-color: #8b949e;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #161b22;
    color: #e6edf3;
    border: 1px solid #30363d;
    selection-background-color: #1f6feb;
    outline: none;
}

/* 按钮 */
QPushButton {
    background-color: #21262d;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 13px;
    min-height: 26px;
}
QPushButton:hover {
    background-color: #30363d;
    border-color: #8b949e;
}
QPushButton:pressed {
    background-color: #1f6feb;
}
QPushButton:disabled {
    color: #484f58;
    background-color: #161b22;
    border-color: #21262d;
}

/* 滑块 */
QSlider::groove:horizontal {
    background: #21262d;
    height: 6px;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #1f6feb;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}
QSlider::handle:horizontal:hover {
    background: #58a6ff;
}
QSlider::sub-page:horizontal {
    background: #1f6feb;
    border-radius: 3px;
}

/* 滚动条 */
QScrollBar:vertical {
    background: #161b22;
    width: 12px;
    border: none;
}
QScrollBar::handle:vertical {
    background: #30363d;
    min-height: 30px;
    border-radius: 6px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover {
    background: #484f58;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: #161b22;
    height: 12px;
    border: none;
}
QScrollBar::handle:horizontal {
    background: #30363d;
    min-width: 30px;
    border-radius: 6px;
    margin: 2px;
}
QScrollBar::handle:horizontal:hover {
    background: #484f58;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* 对话框 */
QDialog {
    background-color: #0d1117;
}
QGroupBox {
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    margin-top: 10px;
    padding: 14px 10px 10px 10px;
    font-size: 13px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
QLabel {
    color: #e6edf3;
    background: transparent;
}
QCheckBox {
    color: #e6edf3;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #30363d;
    border-radius: 3px;
    background: #0d1117;
}
QCheckBox::indicator:checked {
    background: #1f6feb;
    border-color: #1f6feb;
}
QSplitter::handle {
    background-color: #30363d;
}
QSplitter::handle:horizontal { width: 2px; }
QSplitter::handle:vertical { height: 2px; }
QToolTip {
    background-color: #1f6feb;
    color: #e6edf3;
    border: none;
    padding: 6px 10px;
    border-radius: 4px;
    font-size: 12px;
}
QTableWidget {
    background-color: #0d1117;
    color: #e6edf3;
    border: 1px solid #30363d;
    gridline-color: #21262d;
    selection-background-color: #1f6feb22;
    outline: none;
}
QHeaderView::section {
    background-color: #161b22;
    color: #e6edf3;
    border: none;
    border-bottom: 1px solid #30363d;
    padding: 8px;
    font-weight: bold;
}
QSpinBox, QDoubleSpinBox {
    background-color: #0d1117;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 13px;
}
"""


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self._config = AppConfig.load()
        self._processing = False
        self._build_ui()
        self._setup_shortcuts()

    def _build_ui(self):
        self.setWindowTitle(f'{APP_NAME} v{APP_VERSION}')
        self.setMinimumSize(1200, 750)
        self.setStyleSheet(DARK_STYLESHEET)

        # 中央组件
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── 工具栏 ──────────────────────────────────
        self._build_toolbar()

        # ── 主体区域 ────────────────────────────────
        body_splitter = QSplitter(Qt.Horizontal)
        body_splitter.setHandleWidth(2)

        # 左侧：文件列表
        self.file_list = FileListWidget()
        body_splitter.addWidget(self.file_list)

        # 中间：标签页 (预览 + 日志 + 历史)
        center_tabs = QTabWidget()
        center_tabs.setDocumentMode(True)

        # 预览标签
        preview_tab = QWidget()
        preview_layout = QVBoxLayout(preview_tab)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        self.preview = PreviewWidget()
        preview_layout.addWidget(self.preview)
        center_tabs.addTab(preview_tab, '预览')

        # 日志标签
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        log_layout.setContentsMargins(8, 8, 8, 8)
        self.log_widget = LogWidget()
        log_layout.addWidget(self.log_widget)
        center_tabs.addTab(log_tab, '日志')

        # 历史标签
        history_tab = QWidget()
        history_layout = QVBoxLayout(history_tab)
        history_layout.setContentsMargins(8, 8, 8, 8)
        self.history = HistoryWidget()
        history_layout.addWidget(self.history)
        center_tabs.addTab(history_tab, '历史')

        body_splitter.addWidget(center_tabs)

        # 右侧：模板面板
        self.template_panel = TemplatePanel()
        self.template_panel.setMinimumWidth(220)
        self.template_panel.setMaximumWidth(350)
        body_splitter.addWidget(self.template_panel)

        # 设置比例
        body_splitter.setSizes([250, 500, 250])

        main_layout.addWidget(body_splitter, 1)

        # ── 批量处理控制条 ──────────────────────────
        self.batch_control = BatchControlWidget()
        self.log_widget.setMaximumHeight(150)
        self.log_widget.setMinimumHeight(80)

        # 底部分栏: 进度条 + 日志
        bottom_splitter = QSplitter(Qt.Vertical)
        bottom_splitter.setHandleWidth(2)

        # 进度控制
        control_container = QWidget()
        control_layout = QVBoxLayout(control_container)
        control_layout.setContentsMargins(8, 4, 8, 4)
        control_layout.addWidget(self.batch_control)

        bottom_splitter.addWidget(control_container)
        bottom_splitter.addWidget(self.log_widget)
        bottom_splitter.setSizes([80, 120])

        main_layout.addWidget(bottom_splitter)

        # ── 状态栏 ──────────────────────────────────
        status = QStatusBar()
        status.setStyleSheet('QStatusBar { border-top: 1px solid #30363d; }')
        self.setStatusBar(status)

        self.status_label = QLabel('就绪 - 拖拽文件到左侧列表开始')
        status.addWidget(self.status_label, 1)

        self.status_progress = QProgressBar()
        self.status_progress.setRange(0, 100)
        self.status_progress.setValue(0)
        self.status_progress.setFixedWidth(200)
        self.status_progress.setFixedHeight(18)
        self.status_progress.setVisible(False)
        status.addPermanentWidget(self.status_progress)

        # ── 信号连接 ────────────────────────────────

        # 文件列表信号
        self.file_list.file_selected.connect(self._on_file_selected)

        # 批量处理器信号 -> 日志
        worker = self.batch_control  # 简化引用
        worker._on_log = self.log_widget.log_info
        worker._on_log_error = self.log_widget.log_error

        # 批量处理器完成 -> 历史记录
        original_finished = worker._on_all_finished
        def on_finished(summary):
            original_finished(summary)
            self._on_batch_finished(summary)
        worker._on_all_finished = on_finished

        # 批量处理器文件内容 -> 预览
        self.batch_control.file_content_ready.connect(self._on_file_content_result)

        # 批量处理器文件完成 -> 更新状态
        self.batch_control.file_done.connect(self._on_file_done)

        # 模板信号: 更新配置文件中的参数
        self.template_panel.template_changed.connect(self._on_template_changed)

        # 历史记录: 打开结果目录
        self.history.open_result.connect(self._open_result_dir)

        # 文件列表批量操作
        worker._on_file_status = self._on_file_status_update

    def _build_toolbar(self):
        toolbar = QToolBar('主工具栏')
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(18, 18))
        self.addToolBar(toolbar)

        # 添加文件
        add_file_action = QAction('+ 添加文件', self)
        add_file_action.setToolTip('添加文件到列表 (Ctrl+O)')
        add_file_action.triggered.connect(self._toolbar_add_files)
        toolbar.addAction(add_file_action)

        # 添加文件夹
        add_dir_action = QAction('+ 添加文件夹', self)
        add_dir_action.setToolTip('添加文件夹内所有支持的文件 (Ctrl+T)')
        add_dir_action.triggered.connect(self._toolbar_add_directory)
        toolbar.addAction(add_dir_action)

        toolbar.addSeparator()

        # 清空
        clear_action = QAction('× 清空列表', self)
        clear_action.setToolTip('清空文件列表')
        clear_action.triggered.connect(self._toolbar_clear)
        toolbar.addAction(clear_action)

        toolbar.addSeparator()

        # 开始处理
        self.start_action = QAction('▶ 开始处理', self)
        self.start_action.setToolTip('开始批量处理 (F5)')
        self.start_action.triggered.connect(self._toolbar_start)
        toolbar.addAction(self.start_action)

        toolbar.addSeparator()

        # 设置
        settings_action = QAction('⚙ 设置', self)
        settings_action.setToolTip('打开设置 (Ctrl+,)')
        settings_action.triggered.connect(self._open_settings)
        toolbar.addAction(settings_action)

    def _setup_shortcuts(self):
        """设置快捷键"""
        # Ctrl+O 添加文件
        shortcut_add = QAction('添加文件', self)
        shortcut_add.setShortcut(QKeySequence('Ctrl+O'))
        shortcut_add.triggered.connect(self._toolbar_add_files)
        self.addAction(shortcut_add)

        # Ctrl+T 添加文件夹
        shortcut_add_dir = QAction('添加文件夹', self)
        shortcut_add_dir.setShortcut(QKeySequence('Ctrl+T'))
        shortcut_add_dir.triggered.connect(self._toolbar_add_directory)
        self.addAction(shortcut_add_dir)

        # F5 开始处理
        shortcut_start = QAction('开始处理', self)
        shortcut_start.setShortcut(QKeySequence('F5'))
        shortcut_start.triggered.connect(self._toolbar_start)
        self.addAction(shortcut_start)

        # Ctrl+, 设置
        shortcut_settings = QAction('设置', self)
        shortcut_settings.setShortcut(QKeySequence('Ctrl+,'))
        shortcut_settings.triggered.connect(self._open_settings)
        self.addAction(shortcut_settings)

        # Ctrl+L 清空列表
        shortcut_clear = QAction('清空列表', self)
        shortcut_clear.setShortcut(QKeySequence('Ctrl+L'))
        shortcut_clear.triggered.connect(self._toolbar_clear)
        self.addAction(shortcut_clear)

        # Escape 取消
        shortcut_cancel = QAction('取消', self)
        shortcut_cancel.setShortcut(QKeySequence('Escape'))
        shortcut_cancel.triggered.connect(self._cancel_processing)
        self.addAction(shortcut_cancel)

        # Ctrl+P 暂停/继续
        shortcut_pause = QAction('暂停/继续', self)
        shortcut_pause.setShortcut(QKeySequence('Ctrl+P'))
        shortcut_pause.triggered.connect(self._toggle_pause)
        self.addAction(shortcut_pause)

    # ── 工具栏操作 ────────────────────────────────────

    def _toolbar_add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, '选择文件', '',
            '所有支持的文件 (*.docx *.pdf *.txt *.md);;'
            'Word 文档 (*.docx);;PDF 文档 (*.pdf);;'
            '文本文件 (*.txt);;Markdown (*.md);;所有文件 (*.*)'
        )
        if paths:
            self.file_list.add_files([Path(p) for p in paths])

    def _toolbar_add_directory(self):
        directory = QFileDialog.getExistingDirectory(self, '选择文件夹')
        if directory:
            p = Path(directory)
            files = []
            for f in sorted(p.rglob('*')):
                if f.suffix.lower() in SUPPORTED_EXTENSIONS and f.is_file():
                    files.append(f)
            self.file_list.add_files(files)

    def _toolbar_clear(self):
        if self.file_list.get_all_files():
            reply = QMessageBox.question(
                self, '清空', '确定清空所有文件？',
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.file_list.clear_all()
                self.preview.clear_all()

    def _toolbar_start(self):
        self._start_batch_processing()

    def _open_settings(self):
        old_provider = self._config.llm.provider
        new_config = SettingsDialog.edit_config(self._config, self)
        if new_config is not self._config:
            self._config = new_config

    def _cancel_processing(self):
        self.batch_control._cancel()

    def _toggle_pause(self):
        self.batch_control._toggle_pause()

    # ── 业务逻辑 ──────────────────────────────────────

    def _start_batch_processing(self):
        """开始批量处理"""
        files = self.file_list.get_pending_files()
        if not files:
            # 如果没有待处理的，尝试重置所有已完成/失败的文件
            all_files = self.file_list.get_all_files()
            if all_files:
                reply = QMessageBox.question(
                    self, '重新处理',
                    '没有待处理的文件。是否重置所有已完成/失败的文件为待处理？',
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self.file_list.update_all_status(FILE_PENDING)
                    files = self.file_list.get_pending_files()
                else:
                    return
            else:
                QMessageBox.information(self, '提示', '请先添加文件到列表')
                return

        if not files:
            return

        # 获取模板流水线
        pipeline = self.template_panel.get_pipeline()
        if not pipeline:
            QMessageBox.warning(self, '提示', '请选择处理模板')
            return

        # 检查 API 配置
        if not self._config.llm.api_key:
            reply = QMessageBox.question(
                self, 'API 未配置',
                '尚未配置 API Key，是否前往设置？',
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._open_settings()
            return

        # 更新文件状态
        for f in files:
            self.file_list.update_status(f, FILE_PROCESSING)

        paths = [f.path for f in files]

        # 开始处理
        self.batch_control.start_batch(paths, pipeline, self._config)

        self._processing = True
        self.start_action.setText('⏳ 处理中...')
        self.status_label.setText('正在处理...')
        self.status_progress.setVisible(True)
        self.status_progress.setValue(0)

    def _on_file_done(self, idx: int, name: str, success: bool):
        """文件处理完成，更新文件列表状态"""
        all_files = self.file_list.get_all_files()
        if 0 <= idx < len(all_files):
            status = FILE_DONE if success else FILE_FAILED
            self.file_list.update_status(all_files[idx], status)

    def _on_file_selected(self, file_item):
        """选中文件时读取并预览原文"""
        try:
            doc = read_document(file_item.path)
            self.preview.show_original(doc.content, file_item.name)
        except ImportError as e:
            self.preview.show_original(
                f'[无法读取文件]\n需要安装额外依赖: {e}\n\n'
                f'请运行: pip install python-docx pdfplumber PyPDF2',
                file_item.name
            )
        except Exception as e:
            self.preview.show_original(
                f'[读取文件失败]\n{type(e).__name__}: {e}',
                file_item.name
            )

    def _on_file_content_result(self, idx: int, original: str, processed: str):
        """收到处理结果，更新预览"""
        self.preview.show_original(original)
        self.preview.show_result(processed)
        self.status_label.setText(f'文件 {idx+1} 处理完成')

    def _on_template_changed(self, template_id: str, data: dict):
        """模板变更时更新状态栏"""
        from app.template_manager import TemplateManager
        tm = TemplateManager()
        tpl = tm.get(template_id)
        if tpl:
            self.status_label.setText(f'当前模板: {tpl.name}')

    def _on_file_status_update(self, idx: int, status: str):
        """文件状态更新"""
        pass  # 由 file_list 的 update_status 处理

    def _on_batch_finished(self, summary: dict):
        """批量处理完成"""
        self._processing = False
        self.start_action.setText('▶ 开始处理')
        self.status_progress.setVisible(False)

        if summary['fail'] == 0:
            self.status_label.setText(
                f'全部完成! 成功处理 {summary["success"]} 个文件, '
                f'耗时 {summary["duration"]:.1f} 秒'
            )
        else:
            self.status_label.setText(
                f'处理完成: {summary["success"]} 成功, '
                f'{summary["fail"]} 失败, '
                f'耗时 {summary["duration"]:.1f} 秒'
            )

        # 添加到历史记录
        from app.ui_history import HistoryEntry
        from app.template_manager import TemplateManager
        tm = TemplateManager()
        template_name = '流水线'
        pipeline = self.template_panel.get_pipeline()
        if pipeline and len(pipeline) == 1:
            tpl = tm.get(pipeline[0][0])
            if tpl:
                template_name = tpl.name
        elif pipeline:
            names = []
            for tid, _ in pipeline:
                tpl = tm.get(tid)
                names.append(tpl.name if tpl else tid)
            template_name = ' + '.join(names)

        from datetime import datetime
        entry = HistoryEntry({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'template_name': template_name,
            'file_count': summary['total'],
            'success_count': summary['success'],
            'fail_count': summary['fail'],
            'duration': summary['duration'],
            'output_dir': summary.get('output_dir', ''),
        })
        self.history.add_entry(entry)

        # 显示结果汇总
        msg = (
            f'处理完成!\n\n'
            f'总计: {summary["total"]} 个文件\n'
            f'成功: {summary["success"]}\n'
            f'失败: {summary["fail"]}\n'
            f'耗时: {summary["duration"]:.1f} 秒\n\n'
            f'输出目录: {summary.get("output_dir", "")}'
        )
        if summary['fail'] > 0:
            QMessageBox.warning(self, '处理完成', msg)
        else:
            QMessageBox.information(self, '处理完成', msg)

    def _open_result_dir(self, directory: str):
        """打开结果目录"""
        try:
            import subprocess
            subprocess.Popen(['explorer', directory])
        except Exception:
            pass
