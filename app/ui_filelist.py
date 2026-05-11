"""文件列表组件 - 支持拖拽、筛选、状态显示"""

from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QListWidgetItem, QPushButton, QComboBox, QLabel,
    QMenu, QAction, QFileDialog, QMessageBox, QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QMimeData
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QFont, QColor, QPalette, QBrush

from app import (
    FILE_PENDING, FILE_PROCESSING, FILE_DONE, FILE_FAILED,
    STATUS_SYMBOLS, STATUS_COLORS, STATUS_TEXTS,
    FILE_FILTER_ALL, SUPPORTED_EXTENSIONS,
)


class FileItem:
    """文件项目数据"""

    def __init__(self, path: Path):
        self.path = path
        self.name = path.name
        self.size = path.stat().st_size if path.exists() else 0
        self.status = FILE_PENDING
        self.estimated_time = '--'
        self.page_count = 0

    @property
    def size_str(self) -> str:
        if self.size < 1024:
            return f'{self.size} B'
        elif self.size < 1024 * 1024:
            return f'{self.size / 1024:.1f} KB'
        else:
            return f'{self.size / 1024 / 1024:.1f} MB'

    def status_symbol(self) -> str:
        return STATUS_SYMBOLS.get(self.status, '○')

    def status_color(self) -> str:
        return STATUS_COLORS.get(self.status, '#8b949e')

    def status_text(self) -> str:
        return STATUS_TEXTS.get(self.status, '未知')

    def list_text(self) -> str:
        """生成列表显示文本"""
        sym = self.status_symbol()
        return f'{sym}  {self.name}  |  {self.size_str}  |  {self.status_text()}'

    def tooltip_text(self) -> str:
        return (
            f'{self.name}\n'
            f'路径: {self.path}\n'
            f'大小: {self.size_str}\n'
            f'状态: {self.status_text()}\n'
            f'预估时间: {self.estimated_time}'
        )


class FileListWidget(QWidget):
    """文件列表组件"""

    files_added = pyqtSignal(list)        # 添加文件后
    files_removed = pyqtSignal(list)      # 移除文件后
    file_selected = pyqtSignal(object)    # 选中文件 (FileItem)
    selection_changed = pyqtSignal()      # 选择变化

    def __init__(self, parent=None):
        super().__init__(parent)
        self._files: list[FileItem] = []
        self._filter_mode = 'all'
        self._type_filter_mode = 'all'  # 文件类型筛选
        self._build_ui()

        # 启用拖拽
        self.list_widget.setAcceptDrops(True)
        self.list_widget.dragEnterEvent = self._drag_enter_event
        self.list_widget.dragMoveEvent = self._drag_move_event
        self.list_widget.dropEvent = self._drop_event

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 标题
        title = QLabel('📄 文件列表')
        title.setStyleSheet('font-size: 14px; font-weight: bold; padding: 4px 0;')
        layout.addWidget(title)

        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)

        add_btn = QPushButton('+ 添加文件')
        add_btn.setToolTip('添加文件到列表 (Ctrl+O)')
        add_btn.clicked.connect(self._add_files)
        toolbar.addWidget(add_btn)

        add_dir_btn = QPushButton('+ 添加文件夹')
        add_dir_btn.setToolTip('添加文件夹内所有支持的文件 (Ctrl+T)')
        add_dir_btn.clicked.connect(self._add_directory)
        toolbar.addWidget(add_dir_btn)

        clear_btn = QPushButton('× 清空')
        clear_btn.setToolTip('清空文件列表 (Ctrl+L)')
        clear_btn.clicked.connect(self._clear_all)
        toolbar.addWidget(clear_btn)

        toolbar.addStretch()

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(['全部', '待处理', '处理中', '已完成', '失败'])
        self.filter_combo.setToolTip('按状态筛选文件')
        self.filter_combo.currentTextChanged.connect(self._apply_filter)
        toolbar.addWidget(self.filter_combo)

        # 文件类型筛选下拉框
        self.type_combo = QComboBox()
        self.type_combo.addItems(['全部类型', '.docx', '.pdf', '.txt', '.md'])
        self.type_combo.setToolTip('按文件类型筛选')
        self.type_combo.currentTextChanged.connect(self._apply_type_filter)
        toolbar.addWidget(self.type_combo)

        layout.addLayout(toolbar)

        # 列表
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(False)
        self.list_widget.setSpacing(2)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        self.list_widget.currentItemChanged.connect(self._on_selection_changed)
        self.list_widget.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.list_widget)

        # 统计信息
        self.status_label = QLabel('共 0 个文件')
        self.status_label.setStyleSheet('color: #8b949e; font-size: 12px; padding: 2px 0;')
        layout.addWidget(self.status_label)

    # ── 文件操作 ────────────────────────────────────────

    def add_files(self, paths: list[Path]):
        """添加文件到列表"""
        added = []
        for p in paths:
            if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            # 去重
            if any(f.path == p for f in self._files):
                continue
            item = FileItem(p)
            self._files.append(item)
            added.append(item)

        if added:
            self._refresh_list()
            self.files_added.emit(added)

    def remove_files(self, items: list[FileItem]):
        """移除指定文件"""
        for item in items:
            if item in self._files:
                self._files.remove(item)
        self._refresh_list()
        if items:
            self.files_removed.emit(items)

    def clear_completed(self):
        """清除已完成和失败的文件"""
        removed = [f for f in self._files if f.status in (FILE_DONE, FILE_FAILED)]
        self.remove_files(removed)

    def clear_all(self):
        """清空全部"""
        self._files.clear()
        self._refresh_list()
        self.files_removed.emit([])

    def get_selected(self) -> list[FileItem]:
        """获取选中文件"""
        result = []
        for item in self.list_widget.selectedItems():
            idx = self.list_widget.row(item)
            if idx < len(self._filtered_indices):
                fi = self._files[self._filtered_indices[idx]]
                result.append(fi)
        return result

    def get_all_files(self) -> list[FileItem]:
        """获取所有文件"""
        return list(self._files)

    def get_pending_files(self) -> list[FileItem]:
        """获取待处理文件"""
        return [f for f in self._files if f.status == FILE_PENDING]

    def update_status(self, file_item: FileItem, status: int):
        """更新文件状态"""
        file_item.status = status
        self._refresh_list()

    def update_all_status(self, status: int):
        """更新所有文件状态"""
        for f in self._files:
            f.status = status
        self._refresh_list()

    # ── 内部方法 ────────────────────────────────────────

    def _refresh_list(self):
        """刷新列表显示"""
        self.list_widget.clear()
        self._filtered_indices = []

        for i, f in enumerate(self._files):
            # 状态筛选
            if self._filter_mode == 'pending' and f.status != FILE_PENDING:
                continue
            elif self._filter_mode == 'processing' and f.status != FILE_PROCESSING:
                continue
            elif self._filter_mode == 'done' and f.status != FILE_DONE:
                continue
            elif self._filter_mode == 'failed' and f.status != FILE_FAILED:
                continue

            # 文件类型筛选
            if self._type_filter_mode != 'all' and f.path.suffix.lower() != self._type_filter_mode:
                continue

            self._filtered_indices.append(i)

            item = QListWidgetItem(f.list_text())
            item.setData(Qt.UserRole, i)  # 存储原始索引
            item.setToolTip(f.tooltip_text())
            # 根据状态设置文字颜色
            item.setForeground(QColor(f.status_color()))
            self.list_widget.addItem(item)

        self._update_stats()

    def _update_stats(self):
        total = len(self._files)
        pending = sum(1 for f in self._files if f.status == FILE_PENDING)
        done = sum(1 for f in self._files if f.status == FILE_DONE)
        failed = sum(1 for f in self._files if f.status == FILE_FAILED)
        processing = sum(1 for f in self._files if f.status == FILE_PROCESSING)
        self.status_label.setText(
            f'共 {total} 个文件  |  待处理 {pending}  |  处理中 {processing}  |  完成 {done}  |  失败 {failed}'
        )

    def _apply_filter(self, text: str):
        mapping = {'全部': 'all', '待处理': 'pending', '处理中': 'processing', '已完成': 'done', '失败': 'failed'}
        self._filter_mode = mapping.get(text, 'all')
        self._refresh_list()

    def _apply_type_filter(self, text: str):
        """按文件类型筛选"""
        mapping = {'全部类型': 'all', '.docx': '.docx', '.pdf': '.pdf', '.txt': '.txt', '.md': '.md'}
        self._type_filter_mode = mapping.get(text, 'all')
        self._refresh_list()

    # ── 拖拽支持 ────────────────────────────────────────

    def _drag_enter_event(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def _drag_move_event(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def _drop_event(self, event: QDropEvent):
        urls = event.mimeData().urls()
        paths = []
        for url in urls:
            if url.isLocalFile():
                p = Path(url.toLocalFile())
                if p.is_file():
                    paths.append(p)
                elif p.is_dir():
                    # 递归添加目录下支持的文件
                    for f in sorted(p.rglob('*')):
                        if f.suffix.lower() in SUPPORTED_EXTENSIONS and f.is_file():
                            paths.append(f)
        if paths:
            self.add_files(paths)

    # ── 右键菜单 ────────────────────────────────────────

    def _show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        menu = QMenu(self)

        if item is not None:
            remove_action = QAction('移除选中', self)
            remove_action.triggered.connect(lambda: self.remove_files(self.get_selected()))
            menu.addAction(remove_action)

            clear_done_action = QAction('清除已完成/失败', self)
            clear_done_action.triggered.connect(self.clear_completed)
            menu.addAction(clear_done_action)

            menu.addSeparator()

            open_location_action = QAction('打开文件位置', self)
            open_location_action.triggered.connect(self._open_file_location)
            menu.addAction(open_location_action)

            menu.addSeparator()

        # 清空全部 — 即使点空白区域也可访问
        if self._files:
            clear_all_action = QAction('清空全部', self)
            clear_all_action.triggered.connect(self._clear_all)
            menu.addAction(clear_all_action)

        if not menu.isEmpty():
            menu.exec_(self.list_widget.mapToGlobal(pos))

    def _open_file_location(self):
        selected = self.get_selected()
        if selected:
            try:
                import subprocess
                subprocess.Popen(['explorer', '/select,', str(selected[0].path)])
            except Exception:
                pass

    # ── 信号处理 ────────────────────────────────────────

    def _on_selection_changed(self, current, previous):
        self.selection_changed.emit()
        selected = self.get_selected()
        if selected:
            self.file_selected.emit(selected[0])

    def _on_double_click(self, item):
        selected = self.get_selected()
        if selected:
            self.file_selected.emit(selected[0])

    # ── 添加按钮回调 ────────────────────────────────────

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, '选择文件', '', FILE_FILTER_ALL
        )
        if paths:
            self.add_files([Path(p) for p in paths])

    def _add_directory(self):
        directory = QFileDialog.getExistingDirectory(self, '选择文件夹')
        if directory:
            p = Path(directory)
            files = []
            for f in sorted(p.rglob('*')):
                if f.suffix.lower() in SUPPORTED_EXTENSIONS and f.is_file():
                    files.append(f)
            self.add_files(files)

    def _clear_all(self):
        if self._files:
            reply = QMessageBox.question(
                self, '清空文件列表', '确定清空所有文件？',
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.clear_all()
