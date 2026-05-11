"""处理历史记录"""

import json
from datetime import datetime
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QLabel, QHeaderView,
    QMessageBox, QAbstractItemView, QGroupBox,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont


HISTORY_FILE = Path.home() / '.ai-doc-processor' / 'history.json'


class HistoryEntry:
    """历史记录条目"""

    def __init__(self, data: dict):
        self.timestamp: str = data.get('timestamp', '')
        self.template_name: str = data.get('template_name', '')
        self.file_count: int = data.get('file_count', 0)
        self.success_count: int = data.get('success_count', 0)
        self.fail_count: int = data.get('fail_count', 0)
        self.duration: float = data.get('duration', 0)  # 秒
        self.files: list[dict] = data.get('files', [])  # [{path, status}]
        self.output_dir: str = data.get('output_dir', '')

    def to_dict(self) -> dict:
        return {
            'timestamp': self.timestamp,
            'template_name': self.template_name,
            'file_count': self.file_count,
            'success_count': self.success_count,
            'fail_count': self.fail_count,
            'duration': self.duration,
            'files': self.files,
            'output_dir': self.output_dir,
        }

    @property
    def duration_str(self) -> str:
        if self.duration < 60:
            return f'{self.duration:.1f} 秒'
        elif self.duration < 3600:
            return f'{self.duration / 60:.1f} 分'
        else:
            return f'{self.duration / 3600:.1f} 时'


class HistoryWidget(QWidget):
    """历史记录面板"""

    open_result = pyqtSignal(str)  # 打开结果目录

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries: list[HistoryEntry] = []
        self._build_ui()
        self._load_history()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title_layout = QHBoxLayout()
        title = QLabel('📋 处理历史')
        title.setStyleSheet('font-size: 14px; font-weight: bold;')
        title_layout.addWidget(title)
        title_layout.addStretch()

        self.clear_btn = QPushButton('清空历史')
        self.clear_btn.clicked.connect(self._clear_history)
        title_layout.addWidget(self.clear_btn)
        layout.addLayout(title_layout)

        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(['时间', '模板', '文件数', '成功', '失败', '耗时'])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setSortingEnabled(True)
        self.table.itemDoubleClicked.connect(self._on_double_click)

        # 表头样式
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        layout.addWidget(self.table)

        # 提示
        hint = QLabel('双击行打开结果目录')
        hint.setStyleSheet('color: #8b949e; font-size: 11px;')
        layout.addWidget(hint)

    def add_entry(self, entry: HistoryEntry):
        """添加历史记录"""
        self._entries.insert(0, entry)
        self._refresh_table()
        self._save_history()

    def _refresh_table(self):
        """刷新表格"""
        self.table.setRowCount(len(self._entries))
        for row, entry in enumerate(self._entries):
            # 时间
            ts_item = QTableWidgetItem(entry.timestamp)
            ts_item.setData(Qt.UserRole, row)
            ts_item.setForeground(QColor('#8b949e'))
            self.table.setItem(row, 0, ts_item)

            # 模板
            name_item = QTableWidgetItem(entry.template_name)
            name_item.setForeground(QColor('#e6edf3'))
            self.table.setItem(row, 1, name_item)

            # 文件数
            count_item = QTableWidgetItem(str(entry.file_count))
            count_item.setTextAlignment(Qt.AlignCenter)
            count_item.setForeground(QColor('#e6edf3'))
            self.table.setItem(row, 2, count_item)

            # 成功
            success_item = QTableWidgetItem(str(entry.success_count))
            success_item.setTextAlignment(Qt.AlignCenter)
            success_item.setForeground(QColor('#3fb950'))
            self.table.setItem(row, 3, success_item)

            # 失败
            fail_item = QTableWidgetItem(str(entry.fail_count))
            fail_item.setTextAlignment(Qt.AlignCenter)
            fail_item.setForeground(QColor('#f85149') if entry.fail_count > 0 else QColor('#8b949e'))
            self.table.setItem(row, 4, fail_item)

            # 耗时
            dur_item = QTableWidgetItem(entry.duration_str)
            dur_item.setTextAlignment(Qt.AlignCenter)
            dur_item.setForeground(QColor('#e6edf3'))
            self.table.setItem(row, 5, dur_item)

    def _on_double_click(self, item):
        """双击打开结果目录"""
        row = self.table.row(item)
        if 0 <= row < len(self._entries):
            entry = self._entries[row]
            if entry.output_dir and Path(entry.output_dir).exists():
                self.open_result.emit(entry.output_dir)
            else:
                QMessageBox.information(self, '提示', '结果目录不存在或已被删除')

    def _clear_history(self):
        if not self._entries:
            return
        reply = QMessageBox.question(
            self, '清空历史', '确定清空所有处理历史记录？',
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._entries.clear()
            self._refresh_table()
            self._save_history()

    # ── 持久化 ──────────────────────────────────────────

    def _save_history(self):
        try:
            HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = [e.to_dict() for e in self._entries]
            HISTORY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception:
            pass

    def _load_history(self):
        try:
            if HISTORY_FILE.exists():
                data = json.loads(HISTORY_FILE.read_text(encoding='utf-8'))
                self._entries = [HistoryEntry(d) for d in data]
                self._refresh_table()
        except Exception:
            self._entries = []
