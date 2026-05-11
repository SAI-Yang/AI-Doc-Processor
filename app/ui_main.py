"""主窗口 - 浅色主题 + 卡片式布局 + 灵动按钮

重构说明：
  - 浅色主题（白底灰字），卡片式布局，充足留白
  - 圆角按钮 + hover/pressed 动效（颜色渐变、轻微上浮）
  - 文件列表支持拖拽、筛选、状态徽章
  - 预览区域支持"对比/原文/结果"三模式切换
  - 模板卡片蓝色高亮选中
  - 底部进度条（圆角渐变色）+ 实时日志
  - 保持与其他模块的信号接口完全兼容
"""

from pathlib import Path

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTabWidget, QPushButton, QLabel, QFrame,
    QProgressBar, QFileDialog, QMessageBox, QApplication,
    QMenu, QStatusBar, QSizePolicy, QAction, QDialog,
    QTextEdit, QLineEdit,
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QColor, QKeySequence

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
from app.ui_image_dialog import ImageInsertDialog
from app.ui_figure import FigureInsertDialog
from app.ui_generate import GeneratePanel



class MainWindow(QMainWindow):
    """主窗口 - 浅色卡片风格"""

    def __init__(self):
        super().__init__()
        self._config = AppConfig.load()
        self._processing = False
        self._current_docx_path: str = ""
        self._output_dir = str(Path.home() / 'Desktop' / 'AI-处理结果')
        self._mode = 'edit'  # 'edit' | 'generate'

        # 构建 UI 并应用自定义 QSS
        self._build_ui()
        self._setup_shortcuts()

    # ── 主题应用 ────────────────────────────────────────────

    # ── 布局构建 ────────────────────────────────────────────

    def _build_ui(self):
        self.setWindowTitle(f'{APP_NAME} v{APP_VERSION}')
        self.setMinimumSize(1100, 700)

        # 中央组件
        central = QWidget()
        central.setObjectName('centralWidget')
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 0, 16, 12)
        main_layout.setSpacing(10)

        # ── 顶部工具栏 ──────────────────────────────────
        toolbar_widget = self._build_toolbar()
        main_layout.addWidget(toolbar_widget)

        # ── 主体三分栏 ──────────────────────────────────
        body_splitter = QSplitter(Qt.Horizontal)
        body_splitter.setHandleWidth(1)
        body_splitter.setChildrenCollapsible(False)

        # 左侧：文件列表卡片 (30%)
        left_card = QFrame()
        left_card.setObjectName('panelCard')
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        self.file_list = FileListWidget()
        left_layout.addWidget(self.file_list)
        # 文档生成面板（生成模式时显示）
        self.generate_panel = GeneratePanel()
        self.generate_panel.setVisible(False)
        self.generate_panel.set_config(self._config)
        left_layout.addWidget(self.generate_panel)
        body_splitter.addWidget(left_card)

        # 中间：预览面板 (45%)
        center_widget = self._build_preview_panel()
        body_splitter.addWidget(center_widget)

        # 右侧：模板面板卡片 (25%)
        right_card = QFrame()
        right_card.setObjectName('panelCard')
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        self.template_panel = TemplatePanel()
        right_layout.addWidget(self.template_panel)
        body_splitter.addWidget(right_card)

        body_splitter.setSizes([280, 480, 240])
        main_layout.addWidget(body_splitter, 1)

        # ── 底部区域（进度 + 日志）─────────────────────
        bottom_area = self._build_bottom_area()
        main_layout.addWidget(bottom_area)

        # ── 状态栏 ──────────────────────────────────────
        self._build_status_bar()

        # ── 信号连接 ────────────────────────────────────
        self._setup_signals()

        # ── 修复其他组件的暗色内联样式 ──────────────────

        # ── 最后应用自定义 QSS（确保覆盖所有组件）─────

    def _build_toolbar(self):
        """构建顶部工具栏（QPushButton + emoji 图标）"""
        container = QFrame()
        container.setObjectName('toolbarContainer')
        layout = QHBoxLayout(container)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(6)

        # 添加文件（添加文件夹功能移至拖拽和 Ctrl+T 快捷键）
        self.btn_add_file = QPushButton('📁 添加文件')
        self.btn_add_file.setToolTip('添加文件到列表 (Ctrl+O)')
        self.btn_add_file.clicked.connect(self._toolbar_add_files)
        layout.addWidget(self.btn_add_file)

        # 分隔线
        sep1 = QFrame()
        sep1.setObjectName('separator')
        layout.addWidget(sep1)

        # 开始处理
        self.start_action = QPushButton('▶ 开始处理')
        self.start_action.setObjectName('startBtn')
        self.start_action.setToolTip('开始批量处理 (F5)')
        self.start_action.clicked.connect(self._toolbar_start)
        layout.addWidget(self.start_action)

        # 分隔线
        sep2 = QFrame()
        sep2.setObjectName('separator')
        layout.addWidget(sep2)

        # 插入图片（放在设置旁边，不打眼）
        self.btn_insert_image = QPushButton('🖼 插入图片')
        self.btn_insert_image.setToolTip('向文档中插入图片')
        self.btn_insert_image.clicked.connect(self._toolbar_insert_image)
        layout.addWidget(self.btn_insert_image)

        # 生成图表
        self.btn_generate_figure = QPushButton('📊 生成图表')
        self.btn_generate_figure.setToolTip('生成科学图表并插入到文档')
        self.btn_generate_figure.clicked.connect(self._toolbar_generate_figure)
        layout.addWidget(self.btn_generate_figure)

        # 设置
        self.btn_settings = QPushButton('⚙ 设置')
        self.btn_settings.setToolTip('打开设置 (Ctrl+,)')
        self.btn_settings.clicked.connect(self._open_settings)
        layout.addWidget(self.btn_settings)

        # 分隔线
        sep_mode = QFrame()
        sep_mode.setObjectName('separator')
        layout.addWidget(sep_mode)

        # 模式切换
        self.btn_mode_toggle = QPushButton('📝 文档生成')
        self.btn_mode_toggle.setCheckable(True)
        self.btn_mode_toggle.setToolTip('切换到文档生成模式，根据需求描述生成新文档')
        self.btn_mode_toggle.clicked.connect(self._toggle_mode)
        layout.addWidget(self.btn_mode_toggle)

        layout.addStretch()

        # 处理状态指示
        self.toolbar_status = QLabel('就绪')
        layout.addWidget(self.toolbar_status)

        return container

    def _build_preview_panel(self):
        """构建中间预览面板（含视图切换标签）"""
        container = QWidget()
        container.setObjectName('previewPanel')
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 视图切换标签
        header = QFrame()
        header.setObjectName('previewHeader')
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)

        self.tab_compare = QPushButton('对比视图')
        self.tab_compare.setCheckable(True)
        self.tab_compare.setChecked(True)
        self.tab_compare.setCursor(Qt.PointingHandCursor)
        self.tab_compare.clicked.connect(lambda: self._switch_preview_mode('compare'))
        header_layout.addWidget(self.tab_compare)

        self.tab_original = QPushButton('原文')
        self.tab_original.setCheckable(True)
        self.tab_original.setCursor(Qt.PointingHandCursor)
        self.tab_original.clicked.connect(lambda: self._switch_preview_mode('original'))
        header_layout.addWidget(self.tab_original)

        self.tab_result = QPushButton('结果')
        self.tab_result.setCheckable(True)
        self.tab_result.setCursor(Qt.PointingHandCursor)
        self.tab_result.clicked.connect(lambda: self._switch_preview_mode('result'))
        header_layout.addWidget(self.tab_result)

        header_layout.addStretch()

        # 复制/导出按钮
        self.preview_copy_btn = QPushButton('📋 复制')
        self.preview_copy_btn.setToolTip('复制处理结果到剪贴板')
        self.preview_copy_btn.clicked.connect(self._preview_copy)
        self.preview_copy_btn.setEnabled(False)
        header_layout.addWidget(self.preview_copy_btn)

        self.preview_export_btn = QPushButton('💾 导出')
        self.preview_export_btn.setToolTip('导出处理结果到文件')
        self.preview_export_btn.clicked.connect(self._preview_export)
        self.preview_export_btn.setEnabled(False)
        header_layout.addWidget(self.preview_export_btn)

        layout.addWidget(header)

        # 预览组件
        self.preview = PreviewWidget()
        # 隐藏 PreviewWidget 自带的标题栏和按钮（由上层统一管理）
        try:
            for attr in ('title_label', 'copy_btn', 'export_btn'):
                if hasattr(self.preview, attr):
                    getattr(self.preview, attr).setVisible(False)
        except Exception:
            pass
        layout.addWidget(self.preview, 1)

        return container

    def _build_bottom_area(self):
        """构建底部区域（进度条 + 控制按钮 + 日志）"""
        container = QFrame()
        container.setObjectName('bottomArea')
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # 批量处理控制（自带进度条 + 按钮 + 状态列表）
        self.batch_control = BatchControlWidget()
        # 从批处理控制中提取内部组件以便访问
        self._batch_progress_bar = self.batch_control.progress_bar
        self._batch_progress_label = self.batch_control.progress_label

        # 可选：隐藏批处理自身的 start 按钮（由工具栏接管）
        self.batch_control.start_btn.setVisible(False)
        # 批处理的 pause/cancel 按钮保留在底部
        self.batch_control.pause_btn.setObjectName('pauseBtn')
        self.batch_control.cancel_btn.setObjectName('cancelBtn')

        layout.addWidget(self.batch_control)

        # 日志 + 历史标签页
        log_history_tabs = QTabWidget()
        log_history_tabs.setDocumentMode(True)
    
        # 日志标签
        log_tab_widget = QWidget()
        log_tab_layout = QVBoxLayout(log_tab_widget)
        log_tab_layout.setContentsMargins(0, 0, 0, 0)
        log_tab_layout.setSpacing(4)

        # 先创建 LogWidget（后续标题按钮需连接其信号）
        self.log_widget = LogWidget()
        self.log_widget.setObjectName('logWidget')

        # 日志标题 + 清空按钮
        log_header = QHBoxLayout()
        log_header.setSpacing(8)
        log_title = QLabel('📝 处理日志')
        log_header.addWidget(log_title)
        log_header.addStretch()

        self.log_clear_btn = QPushButton('清空')
        self.log_clear_btn.clicked.connect(self.log_widget.clear_log)
        log_header.addWidget(self.log_clear_btn)

        log_tab_layout.addLayout(log_header)
        log_tab_layout.addWidget(self.log_widget, 1)

        log_history_tabs.addTab(log_tab_widget, '📋 日志')

        # 历史标签
        history_tab_widget = QWidget()
        history_tab_layout = QVBoxLayout(history_tab_widget)
        history_tab_layout.setContentsMargins(0, 0, 0, 0)
        history_tab_layout.setSpacing(4)

        self.history = HistoryWidget()
        history_tab_layout.addWidget(self.history, 1)

        log_history_tabs.addTab(history_tab_widget, '📜 历史')

        layout.addWidget(log_history_tabs, 1)

        return container

    def _build_status_bar(self):
        """构建状态栏"""
        status = QStatusBar()
        self.setStatusBar(status)

        self.status_label = QLabel('就绪 — 拖拽文件到左侧列表开始')
        status.addWidget(self.status_label, 1)

        self.status_progress = QProgressBar()
        self.status_progress.setRange(0, 100)
        self.status_progress.setValue(0)
        self.status_progress.setFixedWidth(160)
        self.status_progress.setFixedHeight(16)
        self.status_progress.setVisible(False)
        status.addPermanentWidget(self.status_progress)

    # ── 窗口关闭事件保护 ─────────────────────────────────────

    def closeEvent(self, event):
        """关闭窗口时保护处理，防止 segfault"""
        try:
            if hasattr(self, 'batch_control') and self.batch_control._worker:
                self.batch_control._worker.cancel()
                self.batch_control._worker.wait(2000)
            if hasattr(self, 'generate_panel'):
                self.generate_panel.cancel_generation()
        except Exception:
            pass
        try:
            super().closeEvent(event)
        except Exception:
            pass

    # ── 快捷键 ──────────────────────────────────────────────

    def _setup_shortcuts(self):
        """设置键盘快捷键"""
        shortcut_add = QAction('添加文件', self)
        shortcut_add.setShortcut(QKeySequence('Ctrl+O'))
        shortcut_add.triggered.connect(self._toolbar_add_files)
        self.addAction(shortcut_add)

        shortcut_add_dir = QAction('添加文件夹', self)
        shortcut_add_dir.setShortcut(QKeySequence('Ctrl+T'))
        shortcut_add_dir.triggered.connect(self._toolbar_add_directory)
        self.addAction(shortcut_add_dir)

        shortcut_start = QAction('开始处理', self)
        shortcut_start.setShortcut(QKeySequence('F5'))
        shortcut_start.triggered.connect(self._toolbar_start)
        self.addAction(shortcut_start)

        shortcut_settings = QAction('设置', self)
        shortcut_settings.setShortcut(QKeySequence('Ctrl+,'))
        shortcut_settings.triggered.connect(self._open_settings)
        self.addAction(shortcut_settings)

        shortcut_clear = QAction('清空列表', self)
        shortcut_clear.setShortcut(QKeySequence('Ctrl+L'))
        shortcut_clear.triggered.connect(self._toolbar_clear)
        self.addAction(shortcut_clear)

        shortcut_cancel = QAction('取消', self)
        shortcut_cancel.setShortcut(QKeySequence('Escape'))
        shortcut_cancel.triggered.connect(self._cancel_processing)
        self.addAction(shortcut_cancel)

        shortcut_pause = QAction('暂停/继续', self)
        shortcut_pause.setShortcut(QKeySequence('Ctrl+P'))
        shortcut_pause.triggered.connect(self._toggle_pause)
        self.addAction(shortcut_pause)

    # ── 预览模式切换 ────────────────────────────────────────

    def _switch_preview_mode(self, mode: str):
        """切换预览视图模式"""
        # 更新标签高亮
        self.tab_compare.setChecked(mode == 'compare')
        self.tab_original.setChecked(mode == 'original')
        self.tab_result.setChecked(mode == 'result')

        # 通过 QSplitter 控制分栏大小
        splitter = self.preview.findChild(QSplitter)
        if splitter is None:
            return

        if mode == 'compare':
            splitter.setSizes([400, 400])
            self.preview.original_edit.setVisible(True)
            self.preview.result_edit.setVisible(True)
        elif mode == 'original':
            splitter.setSizes([800, 0])
            self.preview.original_edit.setVisible(True)
            self.preview.result_edit.setVisible(False)
        elif mode == 'result':
            splitter.setSizes([0, 800])
            self.preview.original_edit.setVisible(False)
            self.preview.result_edit.setVisible(True)

    # ── 预览按钮回调 ────────────────────────────────────────

    def _preview_copy(self):
        """复制处理结果"""
        text = self.preview.result_edit.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.status_label.setText('已复制到剪贴板')

    def _preview_export(self):
        """导出处理结果，支持 TXT / DOCX / Markdown"""
        text = self.preview.result_edit.toPlainText()
        if not text:
            return
        base_name = (
            Path(self.preview._file_name).stem if self.preview._file_name else 'result'
        )
        path, _ = QFileDialog.getSaveFileName(
            self, '导出结果', f'{base_name}_processed.txt',
            '文本文件 (*.txt);;Word 文档 (*.docx);;Markdown (*.md);;所有文件 (*.*)'
        )
        if not path:
            return
        try:
            ext = Path(path).suffix.lower()
            if ext == '.docx':
                try:
                    from docx import Document as DocxDoc
                    from docx.shared import Pt
                except ImportError:
                    raise ImportError('请安装 python-docx: pip install python-docx')
                doc = DocxDoc()
                for para_text in text.split('\n'):
                    para_text = para_text.strip()
                    if not para_text:
                        continue
                    p = doc.add_paragraph()
                    run = p.add_run(para_text)
                    run.font.name = 'Times New Roman'
                    run.font.size = Pt(11)
                doc.save(path)
            else:
                Path(path).write_text(text, encoding='utf-8')
            QMessageBox.information(self, '导出成功', f'已保存到:\n{path}')
        except Exception as e:
            QMessageBox.critical(self, '导出失败', str(e))

    # ── 信号连接 ────────────────────────────────────────────

    def _setup_signals(self):
        """连接所有信号（与原有接口完全兼容）"""

        # 文件列表信号
        self.file_list.file_selected.connect(self._on_file_selected)

        # 批量处理器信号 -> 日志
        worker = self.batch_control  # 简化引用
        worker._on_log = self.log_widget.log_info
        worker._on_log_error = self.log_widget.log_error

        # 批量处理器完成 -> 历史记录
        original_finished = worker._on_all_finished
        def on_finished(summary):
            try:
                original_finished(summary)
                self._on_batch_finished(summary)
            except Exception:
                pass
        worker._on_all_finished = on_finished

        # 批量处理器文件内容 -> 预览
        self.batch_control.file_content_ready.connect(self._on_file_content_result)

        # 批量处理器文件完成 -> 更新状态
        self.batch_control.file_done.connect(self._on_file_done)

        # 模板信号
        self.template_panel.template_changed.connect(self._on_template_changed)

        # 历史记录
        self.history.open_result.connect(self._open_result_dir)

        # 文件列表批量操作
        worker._on_file_status = self._on_file_status_update

        # ── 生成面板信号 ────────────────────────────────
        self.generate_panel.chunk_received.connect(self._on_generate_chunk)
        self.generate_panel.generate_started.connect(self._on_generate_started)
        self.generate_panel.generate_finished.connect(self._on_generate_finished)


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
            # 同步配置到生成面板
            self.generate_panel.set_config(self._config)

    def _toolbar_insert_image(self):
        """打开图片插入对话框"""
        if not self._current_docx_path:
            # 尝试从文件列表中取第一个文件
            files = self.file_list.get_all_files()
            if files:
                self._current_docx_path = str(files[0].path)
            else:
                QMessageBox.information(self, '提示', '请先添加并选中一个 .docx 文件')
                return

        path = Path(self._current_docx_path)
        if path.suffix.lower() != '.docx':
            QMessageBox.warning(
                self, '格式不支持',
                '图片插入功能仅支持 .docx 格式文档。\n'
                f'当前文件: {path.name}',
            )
            return

        if not path.exists():
            QMessageBox.warning(self, '文件不存在', f'文件不存在: {path}')
            return

        dialog = ImageInsertDialog(str(path), self)
        dialog.exec_()

    def _toolbar_generate_figure(self):
        """打开图表生成与插入对话框"""
        try:
            docx_path = ""
            if self._current_docx_path:
                p = Path(self._current_docx_path)
                if p.suffix.lower() == '.docx' and p.exists():
                    docx_path = self._current_docx_path
            else:
                # 从文件列表中取第一个 .docx 文件
                files = self.file_list.get_all_files()
                for f in files:
                    if f.path.suffix.lower() == '.docx' and f.path.exists():
                        docx_path = str(f.path)
                        break

            dialog = FigureInsertDialog(docx_path, self)
            dialog.exec_()
        except Exception:
            QMessageBox.critical(
                self, '错误',
                '无法打开图表生成对话框，请确认依赖完整（matplotlib）。',
            )

    # ── 模式切换 ──────────────────────────────────────────────

    def _toggle_mode(self):
        """在文档生成模式和文档编辑模式之间切换"""
        if self._mode == 'edit':
            self._mode = 'generate'
            self.btn_mode_toggle.setText('📄 文档编辑')
            self.btn_mode_toggle.setChecked(True)
            self.btn_mode_toggle.setToolTip('切换到文档编辑模式，处理已有文档')

            # 隐藏编辑模式组件
            self.file_list.setVisible(False)
            self.template_panel.setVisible(False)

            # 隐藏预览头部的视图切换标签（生成模式用不到对比/原文）
            self.tab_compare.setVisible(False)
            self.tab_original.setVisible(False)
            self.tab_result.setVisible(False)
            self.preview_copy_btn.setVisible(False)
            self.preview_export_btn.setVisible(False)

            # 显示生成面板
            self.generate_panel.setVisible(True)
            self.status_label.setText('文档生成模式 — 输入需求描述后点击"生成文档"')
        else:
            self._mode = 'edit'
            self.btn_mode_toggle.setText('📝 文档生成')
            self.btn_mode_toggle.setChecked(False)
            self.btn_mode_toggle.setToolTip('切换到文档生成模式，根据需求描述生成新文档')

            # 取消正在进行的生成任务
            self.generate_panel.cancel_generation()

            # 隐藏生成面板
            self.generate_panel.setVisible(False)

            # 恢复编辑模式组件
            self.file_list.setVisible(True)
            self.template_panel.setVisible(True)
            self.tab_compare.setVisible(True)
            self.tab_original.setVisible(True)
            self.tab_result.setVisible(True)
            self.preview_copy_btn.setVisible(True)
            self.preview_export_btn.setVisible(True)

            self.status_label.setText('就绪 — 拖拽文件到左侧列表开始')

    # ── 文档生成信号处理 ──────────────────────────────────────

    def _on_generate_started(self):
        """开始生成文档"""
        # 清空预览
        self.preview.show_original('')
        self.preview.show_result('')
        self.status_label.setText('⏳ 正在生成文档...')
        # 切换到结果视图，只显示生成中的文本
        self._switch_preview_mode('result')

    def _on_generate_chunk(self, chunk: str):
        """收到流式文本块 — 实时更新预览（通过 show_result 全量刷新）"""
        # 累积的完整文本通过 finished 信号一次性更新，
        # 这里仅做状态提示
        pass

    def _on_generate_finished(self, text: str):
        """文档生成完成"""
        if text.strip():
            self.preview.show_result(text)
            self._switch_preview_mode('result')
            # 启用复制/导出
            self.preview_copy_btn.setEnabled(True)
            self.preview_export_btn.setEnabled(True)
            char_count = len(text)
            self.status_label.setText(
                f'文档生成完成 — 共 {char_count} 字符'
            )
        else:
            self.status_label.setText('文档生成完毕，内容为空')

    def _cancel_processing(self):
        """取消批量处理"""
        if hasattr(self, 'batch_control'):
            self.batch_control._cancel()

    def _toggle_pause(self):
        """暂停/继续批量处理"""
        if hasattr(self, 'batch_control'):
            self.batch_control._toggle_pause()

    # ── 业务逻辑（与原有接口完全兼容）──────────────────────

    def _start_batch_processing(self):
        """开始批量处理（带预览确认）"""
        # 1. 获取待处理文件
        files = self.file_list.get_pending_files()
        if not files:
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

        # 2. 获取处理流水线
        pipeline = self.template_panel.get_pipeline()
        if not pipeline:
            QMessageBox.warning(self, '提示', '请选择处理模板')
            return

        if not self._config.llm.api_key:
            reply = QMessageBox.question(
                self, 'API 未配置',
                '尚未配置 API Key，是否前往设置？',
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._open_settings()
            return

        paths = [f.path for f in files]

        # 3. 选择输出目录（记住上次选择）
        default_out = self._config.output_dir or str(Path.home() / 'Desktop' / 'AI-处理结果')
        out_dir = QFileDialog.getExistingDirectory(
            self, '选择输出目录', default_out,
            QFileDialog.ShowDirsOnly
        )
        if not out_dir:
            return  # 用户取消
        self._output_dir = out_dir
        self._config.output_dir = out_dir
        self._config.save()

        # 4. 预览确认：用第一个文件展示 AI 处理效果，用户确认后再执行
        if not self._show_preview_and_confirm(paths[0], pipeline):
            self.status_label.setText('已取消处理')
            return

        # 4. 用户确认后正式开始批量处理
        for f in files:
            self.file_list.update_status(f, FILE_PROCESSING)

        self.batch_control.start_batch(paths, pipeline, self._config, self._output_dir)

        self._processing = True
        self.start_action.setText('⏳ 处理中...')
        self.start_action.setEnabled(False)
        self.status_label.setText('正在处理...')
        self.status_progress.setVisible(True)
        self.status_progress.setValue(0)
        self.toolbar_status.setText('⏳ 处理中...')

    # ── 处理前预览确认 ─────────────────────────────────────────

    def _show_preview_and_confirm(self, file_path: Path, pipeline: list) -> bool:
        """处理前预览确认：调用 LLM 处理首个文件，展示结果供用户确认

        流程：
          1. 读取第一个文档
          2. 快速调用 LLM（降低 max_tokens 加速返回）
          3. 展示 PreviewConfirmDialog（原文 | 结果对比）
          4. 用户确认 → 继续批量 / 取消 → 不做处理

        Args:
            file_path: 第一个待处理文件的路径
            pipeline: 处理流水线 [(template_id, data), ...]

        Returns:
            True  用户确认处理
            False 用户取消处理（或预览失败且用户选择不继续）
        """
        import asyncio
        import copy
        from app.document import read_document
        from app.template_manager import TemplateManager
        from app.llm_client import create_client

        # 读取文档
        try:
            doc = read_document(file_path)
            original_text = doc.content
        except Exception as e:
            logger.warning("预览：读取文件失败 %s — %s", file_path.name, e)
            # 文件读取失败，询问是否直接跳过预览继续处理
            reply = QMessageBox.question(
                self, '读取失败',
                f'无法读取文件:\n{file_path.name}\n{type(e).__name__}: {e}\n\n'
                '是否跳过预览直接处理？',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            return reply == QMessageBox.Yes

        if not original_text.strip():
            # 空文档无需预览
            return True

        # 更新状态栏，提示用户正在生成预览
        self.status_label.setText('⏳ 正在生成处理预览...')
        self.toolbar_status.setText('⏳ 预览中')
        self.start_action.setEnabled(False)
        self.start_action.setText('⏳ 预览中...')
        QApplication.processEvents()

        try:
            # 预览全部内容（不截断）
            PREVIEW_MAX_CHARS = 50000
            preview_text = original_text[:PREVIEW_MAX_CHARS]
            if len(original_text) > PREVIEW_MAX_CHARS:
                preview_text += '\n\n[文档较长，预览仅显示前50000字符]'

            template_mgr = TemplateManager()
            current_text = preview_text
            last_user_prompt = ''

            # 逐步骤处理（仅预览第一份文件的第一段）
            for tid, tdata in pipeline:
                tpl = template_mgr.get(tid)
                if tpl:
                    system_prompt = tpl.system_prompt
                    user_prompt = tpl.user_prompt.replace('{content}', current_text)
                    if '{text}' in user_prompt:
                        user_prompt = user_prompt.replace('{text}', current_text)
                else:
                    system_prompt = tdata.get('system_prompt', '')
                    raw = tdata.get('user_prompt', '')
                    user_prompt = raw.replace('{text}', current_text)
                    user_prompt = user_prompt.replace('{content}', current_text)
                    # 如果没写占位符，自动追加文档内容
                    if '{content}' not in raw and '{text}' not in raw and raw.strip():
                        user_prompt = raw + '\n\n---\n' + current_text

                last_user_prompt = user_prompt

                # 预览模式：降低 max_tokens 加速返回
                step_config = copy.copy(self._config.llm)
                step_config.max_tokens = min(step_config.max_tokens, 1024)
                client = create_client(step_config)

                processed = asyncio.run(client.process_content(
                    content=current_text,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                ))
                current_text = processed.strip() or current_text

        except ImportError as e:
            # 依赖缺失（如 python-docx），跳过预览直接处理
            logger.warning("预览缺少依赖，跳过预览: %s", e)
            return True
        except Exception as e:
            logger.error("预览生成失败: %s", e)
            reply = QMessageBox.question(
                self, '预览失败',
                f'无法生成处理预览:\n{type(e).__name__}: {str(e)[:200]}\n\n'
                '是否跳过预览直接处理？',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            return reply == QMessageBox.Yes
        finally:
            # 恢复 UI 状态
            self.start_action.setEnabled(True)
            self.start_action.setText('▶ 开始处理')
            self.toolbar_status.setText('就绪')

        # 展示预览确认对话框
        dialog = PreviewConfirmDialog(
            original_text=original_text,
            result_text=current_text,
            prompt_text=last_user_prompt,
            parent=self,
        )
        return dialog.exec_() == QDialog.Accepted

    def _on_file_done(self, idx: int, name: str, success: bool):
        """文件处理完成，更新文件列表状态"""
        all_files = self.file_list.get_all_files()
        if 0 <= idx < len(all_files):
            status = FILE_DONE if success else FILE_FAILED
            self.file_list.update_status(all_files[idx], status)

    def _on_file_selected(self, file_item):
        """选中文件时读取并预览原文"""
        self._current_docx_path = str(file_item.path)
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
        # 获取源文件路径和可能的输出文件路径，供文档模式预览使用
        original_file = None
        result_file = None
        all_files = self.file_list.get_all_files()
        if 0 <= idx < len(all_files):
            file_item = all_files[idx]
            original_file = file_item.path
            # 尝试构造输出文件路径（与 BatchWorker 约定一致）
            if hasattr(self, '_output_dir') and self._output_dir:
                out_dir = Path(self._output_dir)
                if out_dir.exists():
                    # 扫描 session 子目录，查找匹配的处理后文件
                    stem = file_item.path.stem
                    suffix = file_item.path.suffix
                    candidates = sorted(out_dir.rglob(f'{stem}_processed{suffix}'))
                    if candidates:
                        result_file = candidates[-1]  # 最新的匹配文件

        self.preview.set_content(
            original, processed,
            original_file=original_file,
            result_file=result_file,
        )
        self.status_label.setText(f'文件 {idx+1} 处理完成')

        # 启用复制/导出按钮
        if processed.strip():
            self.preview_copy_btn.setEnabled(True)
            self.preview_export_btn.setEnabled(True)

    def _on_template_changed(self, template_id: str, data: dict):
        """模板/提示词变更时更新状态栏，显示提示词前 40 字"""
        if template_id == 'custom':
            prompt = data.get('user_prompt', '')
            if prompt.strip():
                preview = prompt.strip()[:40]
                suffix = '...' if len(prompt.strip()) > 40 else ''
                self.status_label.setText(f'提示词: {preview}{suffix}')
            else:
                self.status_label.setText('就绪 — 输入处理提示词后开始处理')
            return
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
        self.start_action.setEnabled(True)
        self.status_progress.setVisible(False)
        self.toolbar_status.setText('就绪')

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


# ═══════════════════════════════════════════════════════════════
#  PreviewConfirmDialog — 处理前预览确认对话框
# ═══════════════════════════════════════════════════════════════

class PreviewConfirmDialog(QDialog):
    """处理前预览确认对话框

    左右分栏显示「原文 | AI 处理结果」，
    用户确认后继续批量处理，取消则回退。
    """

    def __init__(self, original_text: str, result_text: str,
                 prompt_text: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle('处理预览 - 确认或取消')
        self.setMinimumSize(800, 500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── 顶部提示条 ──────────────────────────────────
        info_bar = QLabel(
            '  预览：下方显示 AI 将如何修改文档。'
            '确认无误后点击"确认处理"，否则点击"取消"调整模板。'
        )
        info_bar.setStyleSheet(
            'background: #e3f2fd; color: #1565c0;'
            ' padding: 8px 16px; font-size: 12px;'
        )
        layout.addWidget(info_bar)

        # ── 左右分栏 ────────────────────────────────────
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：原文
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(12, 12, 6, 12)

        left_header = QLabel('📄 原文')
        left_header.setStyleSheet(
            'font-weight: bold; font-size: 13px; color: #555;'
            ' margin-bottom: 4px;'
        )
        left_layout.addWidget(left_header)

        self.orig_edit = QTextEdit()
        self.orig_edit.setPlainText(original_text)
        self.orig_edit.setReadOnly(True)
        self.orig_edit.setStyleSheet(
            'QTextEdit { background: #f8f9fa; border: 1px solid #e0e0e0;'
            ' border-radius: 4px; padding: 8px; font-size: 13px; }'
        )
        left_layout.addWidget(self.orig_edit, 1)
        splitter.addWidget(left_widget)

        # 右侧：处理结果
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(6, 12, 12, 12)

        right_header = QLabel('✨ AI 处理结果')
        right_header.setStyleSheet(
            'font-weight: bold; font-size: 13px; color: #2e7d32;'
            ' margin-bottom: 4px;'
        )
        right_layout.addWidget(right_header)

        self.result_edit = QTextEdit()
        self.result_edit.setPlainText(result_text)
        self.result_edit.setReadOnly(True)
        self.result_edit.setStyleSheet(
            'QTextEdit { background: #ffffff; border: 1px solid #e0e0e0;'
            ' border-radius: 4px; padding: 8px; font-size: 13px; }'
        )
        right_layout.addWidget(self.result_edit, 1)
        splitter.addWidget(right_widget)

        layout.addWidget(splitter, 1)

        # ── 底部按钮栏 ──────────────────────────────────
        btn_bar = QFrame()
        btn_bar.setStyleSheet(
            'QFrame { background: #f8f9fa;'
            ' border-top: 1px solid #e0e0e0; }'
        )
        btn_layout = QHBoxLayout(btn_bar)
        btn_layout.setContentsMargins(16, 8, 16, 8)
        btn_layout.setSpacing(8)

        # 提示词展示
        prompt_label = QLabel('当前提示词:')
        prompt_label.setStyleSheet(
            'color: #666; font-size: 12px; font-weight: 500;'
        )
        btn_layout.addWidget(prompt_label)

        prompt_display = QLabel(
            prompt_text[:80] + ('...' if len(prompt_text) > 80 else '')
        )
        prompt_display.setStyleSheet(
            'color: #888; font-size: 12px; font-style: italic;'
        )
        prompt_display.setWordWrap(True)
        btn_layout.addWidget(prompt_display, 1)

        btn_layout.addStretch()

        # 取消按钮
        self.btn_cancel = QPushButton('取消')
        self.btn_cancel.setStyleSheet(
            'QPushButton { padding: 6px 24px;'
            ' border: 1px solid #ccc; border-radius: 4px;'
            ' background: white; font-size: 13px; }'
            'QPushButton:hover { background: #f5f5f5; }'
        )
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        # 确认处理按钮
        self.btn_confirm = QPushButton('✅ 确认处理')
        self.btn_confirm.setStyleSheet(
            'QPushButton { padding: 6px 24px; border: none;'
            ' border-radius: 4px; background: #1976d2;'
            ' color: white; font-size: 13px; font-weight: bold; }'
            'QPushButton:hover { background: #1565c0; }'
        )
        self.btn_confirm.clicked.connect(self.accept)
        self.btn_confirm.setDefault(True)
        btn_layout.addWidget(self.btn_confirm)

        layout.addWidget(btn_bar)
