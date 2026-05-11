"""处理预览组件 - 原文/结果对比，高亮差异，统计，导出"""

import difflib
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTextEdit, QLabel, QPushButton, QFrame,
    QFileDialog, QMessageBox, QSizePolicy, QToolButton,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QTextCursor, QColor, QTextCharFormat, QTextDocument


class PreviewWidget(QWidget):
    """预览组件 - 左右分栏对比"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._original_text = ''
        self._processed_text = ''
        self._file_name = ''
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 标签栏
        title_layout = QHBoxLayout()

        self.title_label = QLabel('预览')
        self.title_label.setStyleSheet('font-size: 14px; font-weight: bold; padding: 4px 0;')
        title_layout.addWidget(self.title_label)

        title_layout.addStretch()

        self.copy_btn = QPushButton('📋 复制结果')
        self.copy_btn.setToolTip('复制处理结果到剪贴板')
        self.copy_btn.clicked.connect(self._copy_result)
        self.copy_btn.setEnabled(False)
        title_layout.addWidget(self.copy_btn)

        self.export_btn = QPushButton('💾 导出')
        self.export_btn.setToolTip('导出处理结果到文件')
        self.export_btn.clicked.connect(self._export_result)
        self.export_btn.setEnabled(False)
        title_layout.addWidget(self.export_btn)

        layout.addLayout(title_layout)

        # 统计信息
        self.stats_label = QLabel('字数: 0  |  字符: 0')
        self.stats_label.setStyleSheet('color: #8b949e; font-size: 12px;')
        layout.addWidget(self.stats_label)

        # 左右分栏
        splitter = QSplitter(Qt.Horizontal)

        # 原文面板
        original_panel = QWidget()
        original_layout = QVBoxLayout(original_panel)
        original_layout.setContentsMargins(0, 0, 0, 0)
        original_layout.setSpacing(2)

        original_header = QLabel('原文')
        original_header.setStyleSheet(
            'font-size: 12px; font-weight: bold; color: #8b949e; '
            'padding: 4px 8px; background-color: #161b22; '
            'border: 1px solid #30363d; border-bottom: none; border-radius: 4px 4px 0 0;'
        )
        original_layout.addWidget(original_header)

        self.original_edit = QTextEdit()
        self.original_edit.setReadOnly(True)
        self.original_edit.setFont(QFont('Consolas', 12))
        self.original_edit.setPlaceholderText('选择文件后在此显示原文内容')
        original_layout.addWidget(self.original_edit)

        splitter.addWidget(original_panel)

        # 结果面板
        result_panel = QWidget()
        result_layout = QVBoxLayout(result_panel)
        result_layout.setContentsMargins(0, 0, 0, 0)
        result_layout.setSpacing(2)

        result_header = QLabel('处理结果')
        result_header.setStyleSheet(
            'font-size: 12px; font-weight: bold; color: #3fb950; '
            'padding: 4px 8px; background-color: #161b22; '
            'border: 1px solid #30363d; border-bottom: none; border-radius: 4px 4px 0 0;'
        )
        result_layout.addWidget(result_header)

        self.result_edit = QTextEdit()
        self.result_edit.setReadOnly(True)
        self.result_edit.setFont(QFont('Consolas', 12))
        self.result_edit.setPlaceholderText('处理完成后在此显示结果')
        result_layout.addWidget(self.result_edit)

        splitter.addWidget(result_panel)

        splitter.setSizes([400, 400])
        layout.addWidget(splitter, 1)

    # ── 显示内容 ────────────────────────────────────────

    def show_original(self, text: str, file_name: str = ''):
        """显示原文"""
        self._original_text = text
        if file_name:
            self._file_name = file_name
            self.title_label.setText(f'预览 - {file_name}')
        self.original_edit.setPlainText(text)
        self._update_stats()

    def show_result(self, text: str):
        """显示处理结果"""
        self._processed_text = text
        self.result_edit.setPlainText(text)
        self._show_diff()
        self._update_stats()
        self.copy_btn.setEnabled(bool(text.strip()))
        self.export_btn.setEnabled(bool(text.strip()))

    def show_diff_highlight(self, original: str, processed: str):
        """显示带高亮差异的对比"""
        self.original_edit.setPlainText(original)
        self._apply_diff_highlight(original, processed)
        self._update_stats()

    def _show_diff(self):
        """用 HTML 显示差异高亮"""
        if not self._original_text or not self._processed_text:
            return

        orig_lines = self._original_text.splitlines()
        proc_lines = self._processed_text.splitlines()

        # 生成并排 diff HTML
        differ = difflib.HtmlDiff(tabsize=4)
        diff_html = differ.make_table(
            orig_lines, proc_lines,
            context=True, numlines=3,
        )

        # 包裹样式
        styled_html = f"""<html><body style="background:#0d1117; color:#e6edf3;
        font-family: Consolas, monospace; font-size: 12px;">
        {diff_html}</body></html>"""

        # 显示在 result 面板中
        self.result_edit.setHtml(styled_html)

    def _apply_diff_highlight(self, original: str, processed: str):
        """在 result 面板应用行级别的高亮"""
        # 使用 difflib 比较
        differ = difflib.SequenceMatcher(None, original.splitlines(), processed.splitlines())
        self.result_edit.clear()

        cursor = self.result_edit.textCursor()

        add_fmt = QTextCharFormat()
        add_fmt.setBackground(QColor('#3fb95033'))
        add_fmt.setForeground(QColor('#3fb950'))

        del_fmt = QTextCharFormat()
        del_fmt.setBackground(QColor('#f8514933'))
        del_fmt.setForeground(QColor('#f85149'))

        normal_fmt = QTextCharFormat()
        normal_fmt.setForeground(QColor('#e6edf3'))

        proc_lines = processed.splitlines()

        for tag, i1, i2, j1, j2 in differ.get_opcodes():
            if tag == 'equal':
                for line in proc_lines[j1:j2]:
                    cursor.insertText(line + '\n', normal_fmt)
            elif tag == 'replace':
                for line in proc_lines[j1:j2]:
                    cursor.insertText(line + '\n', add_fmt)
            elif tag == 'delete':
                pass  # 删除的不在结果中显示
            elif tag == 'insert':
                for line in proc_lines[j1:j2]:
                    cursor.insertText(line + '\n', add_fmt)

    # ── 统计 ─────────────────────────────────────────────

    def _update_stats(self):
        orig = self.original_edit.toPlainText()
        result = self.result_edit.toPlainText()

        orig_words = len(orig.split())
        orig_chars = len(orig.replace(' ', '').replace('\n', ''))
        result_words = len(result.split())
        result_chars = len(result.replace(' ', '').replace('\n', ''))

        self.stats_label.setText(
            f'原文: {orig_words} 词 / {orig_chars} 字  |  '
            f'结果: {result_words} 词 / {result_chars} 字  |  '
            f'差异: {result_chars - orig_chars:+d} 字'
        )

    # ── 操作 ─────────────────────────────────────────────

    def _copy_result(self):
        """复制结果到剪贴板"""
        text = self.result_edit.toPlainText()
        if text:
            from PyQt5.QtWidgets import QApplication
            QApplication.clipboard().setText(text)

    def _export_result(self):
        """导出结果到文件"""
        if not self._processed_text:
            return

        default_name = Path(self._file_name).stem + '_processed.txt' if self._file_name else 'result.txt'
        path, _ = QFileDialog.getSaveFileName(
            self, '导出结果', default_name,
            '文本文件 (*.txt);;Markdown (*.md);;所有文件 (*.*)'
        )
        if path:
            try:
                Path(path).write_text(self._processed_text, encoding='utf-8')
                QMessageBox.information(self, '导出成功', f'已保存到:\n{path}')
            except Exception as e:
                QMessageBox.critical(self, '导出失败', str(e))

    def clear_all(self):
        """清空所有内容"""
        self._original_text = ''
        self._processed_text = ''
        self._file_name = ''
        self.original_edit.clear()
        self.result_edit.clear()
        self.title_label.setText('预览')
        self.stats_label.setText('字数: 0  |  字符: 0')
        self.copy_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
