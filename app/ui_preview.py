"""处理预览组件 - 原文/结果对比，高亮差异，统计，导出"""

import difflib
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTextEdit, QPlainTextEdit, QLabel, QPushButton,
    QFileDialog, QMessageBox, QTabWidget,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QTextCursor, QColor, QTextCharFormat


class PreviewWidget(QWidget):
    """预览组件 - 对比/原文/结果三视图 + 差异高亮 + 导出"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._original_text = ''
        self._processed_text = ''
        self._file_name = ''
        self._process_time = 0.0
        self._build_ui()

    def _build_ui(self):
        """构建完整 UI：内边距 16px 的浅色主题"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self._build_top_bar(layout)
        self._build_center_area(layout)
        self._build_bottom_bar(layout)

        self._update_all()

    # ── 顶部：文件名标签 ────────────────────────────────

    def _build_top_bar(self, parent_layout):
        """文件名标签 + 统计信息"""
        file_layout = QHBoxLayout()
        file_layout.setSpacing(8)

        self.original_name_label = QLabel('原文: ')
        self.original_name_label.setStyleSheet(
            'font-size: 13px; font-weight: bold; color: #333;'
            'background: #f0f0f0; padding: 4px 12px; border-radius: 4px;'
        )

        arrow_label = QLabel('→')
        arrow_label.setStyleSheet('font-size: 16px; color: #999;')
        file_layout.addWidget(self.original_name_label)
        file_layout.addWidget(arrow_label)

        self.result_name_label = QLabel('结果: ')
        self.result_name_label.setStyleSheet(
            'font-size: 13px; font-weight: bold; color: #333;'
            'background: #e8f5e9; padding: 4px 12px; border-radius: 4px;'
        )
        file_layout.addWidget(self.result_name_label)
        file_layout.addStretch()
        parent_layout.addLayout(file_layout)

        # 统计信息
        self.stats_label = QLabel('字数: 0  |  耗时: --')
        self.stats_label.setStyleSheet('color: #888; font-size: 12px;')
        parent_layout.addWidget(self.stats_label)

    # ── 中间：选项卡 + 三视图 ────────────────────────────

    def _build_center_area(self, parent_layout):
        """选项卡（对比/原文/结果）+ 对应视图"""
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #ddd; border-radius: 4px;
                background: white; padding: 0px;
            }
            QTabBar::tab {
                padding: 8px 20px; font-size: 13px; color: #555;
                border: none;
            }
            QTabBar::tab:selected {
                background: white;
                border-bottom: 2px solid #1976d2;
                color: #1976d2;
            }
            QTabBar::tab:!selected {
                background: #f5f5f5;
            }
            QTabBar::tab:hover:!selected {
                background: #e8e8e8;
            }
        """)

        self._build_compare_tab()
        self._build_original_tab()
        self._build_result_tab()

        parent_layout.addWidget(self.tab_widget, 1)

    def _build_compare_tab(self):
        """对比视图：QSplitter 左右分栏 + 差异高亮"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(6)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background: #e0e0e0;
                border: none;
            }
            QSplitter::handle:hover {
                background: #1976d2;
            }
        """)

        # ── 左侧：原文面板（灰底） ──
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(4)

        left_header = QLabel('原文')
        left_header.setStyleSheet('font-weight: bold; font-size: 12px; color: #666;')
        left_layout.addWidget(left_header)

        self.orig_diff_edit = QTextEdit()
        self.orig_diff_edit.setReadOnly(True)
        self.orig_diff_edit.document().setMaximumBlockCount(0)
        self.orig_diff_edit.setFont(QFont('Consolas', 12))
        self.orig_diff_edit.setPlaceholderText('暂无内容')
        self.orig_diff_edit.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa; color: #000;
                border: 1px solid #e0e0e0; border-radius: 4px;
                padding: 8px;
            }
        """)
        left_layout.addWidget(self.orig_diff_edit)

        splitter.addWidget(left_panel)

        # ── 右侧：结果面板（白底） ──
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(4)

        right_header = QLabel('结果')
        right_header.setStyleSheet('font-weight: bold; font-size: 12px; color: #666;')
        right_layout.addWidget(right_header)

        self.result_diff_edit = QTextEdit()
        self.result_diff_edit.setReadOnly(True)
        self.result_diff_edit.document().setMaximumBlockCount(0)
        self.result_diff_edit.setFont(QFont('Consolas', 12))
        self.result_diff_edit.setPlaceholderText('暂无内容')
        self.result_diff_edit.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff; color: #000;
                border: 1px solid #e0e0e0; border-radius: 4px;
                padding: 8px;
            }
        """)
        right_layout.addWidget(self.result_diff_edit)

        splitter.addWidget(right_panel)

        splitter.setSizes([500, 500])
        layout.addWidget(splitter, 1)

        self.tab_widget.addTab(container, '对比')

    def _build_original_tab(self):
        """原文单独视图 — 可编辑的 QPlainTextEdit"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)

        self.original_edit = QPlainTextEdit()
        self.original_edit.setFont(QFont('Consolas', 12))
        self.original_edit.setPlaceholderText('暂无内容')
        self.original_edit.document().setMaximumBlockCount(0)  # 无段落上限
        self.original_edit.setStyleSheet("""
            QPlainTextEdit {
                background-color: #f8f9fa; color: #000;
                border: 1px solid #e0e0e0; border-radius: 4px;
                padding: 8px;
            }
        """)
        layout.addWidget(self.original_edit)

        self.tab_widget.addTab(container, '原文')

    def _build_result_tab(self):
        """结果单独视图 — 只读 QPlainTextEdit，支持选中复制"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)

        self.result_edit = QPlainTextEdit()
        self.result_edit.setReadOnly(True)
        self.result_edit.document().setMaximumBlockCount(0)  # 无段落上限
        self.result_edit.setFont(QFont('Consolas', 12))
        self.result_edit.setPlaceholderText('暂无内容')
        self.result_edit.setStyleSheet("""
            QPlainTextEdit {
                background-color: #ffffff; color: #000;
                border: 1px solid #e0e0e0; border-radius: 4px;
                padding: 8px;
            }
        """)
        layout.addWidget(self.result_edit)

        self.tab_widget.addTab(container, '结果')

    # ── 底部：导出按钮组 ────────────────────────────────

    def _build_bottom_bar(self, parent_layout):
        """导出按钮组：TXT / Markdown / 复制到剪贴板"""
        btn_style = """
            QPushButton {
                padding: 6px 16px; font-size: 12px;
                border: 1px solid #ccc; border-radius: 4px;
                background: #fafafa; color: #333;
            }
            QPushButton:hover {
                background: #e8e8e8; border-color: #aaa;
            }
            QPushButton:disabled {
                color: #bbb; background: #f5f5f5; border-color: #e0e0e0;
            }
            QPushButton:pressed {
                background: #d5d5d5;
            }
        """

        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(8)

        self.export_txt_btn = QPushButton('\U0001F4C4 导出为 TXT')
        self.export_txt_btn.setToolTip('保存为 .txt 文件')
        self.export_txt_btn.clicked.connect(lambda: self._export_result('txt'))
        self.export_txt_btn.setEnabled(False)
        self.export_txt_btn.setStyleSheet(btn_style)

        self.export_md_btn = QPushButton('\U0001F4DD 导出为 Markdown')
        self.export_md_btn.setToolTip('保存为 .md 文件')
        self.export_md_btn.clicked.connect(lambda: self._export_result('md'))
        self.export_md_btn.setEnabled(False)
        self.export_md_btn.setStyleSheet(btn_style)

        self.export_docx_btn = QPushButton('\U0001F4C4 导出为 DOCX')
        self.export_docx_btn.setToolTip('保存为 .docx 文件（保留基本格式）')
        self.export_docx_btn.clicked.connect(lambda: self._export_result('docx'))
        self.export_docx_btn.setEnabled(False)
        self.export_docx_btn.setStyleSheet(btn_style)

        self.copy_btn = QPushButton('\U0001F4CB 复制到剪贴板')
        self.copy_btn.setToolTip('一键复制处理结果')
        self.copy_btn.clicked.connect(self._copy_result)
        self.copy_btn.setEnabled(False)
        self.copy_btn.setStyleSheet(btn_style)

        bottom_layout.addWidget(self.export_txt_btn)
        bottom_layout.addWidget(self.export_md_btn)
        bottom_layout.addWidget(self.export_docx_btn)
        bottom_layout.addWidget(self.copy_btn)
        bottom_layout.addStretch()

        parent_layout.addLayout(bottom_layout)

    # ── Diff 差异对比 ───────────────────────────────────

    def _compute_char_diff(self, original: str, processed: str):
        """字符级 diff，返回 difflib.SequenceMatcher opcodes 列表"""
        matcher = difflib.SequenceMatcher(None, original, processed)
        return matcher.get_opcodes()

    def _apply_diff_highlight(self, original: str, processed: str, opcodes):
        """将 diff opcodes 应用到左右两个对比编辑框

        颜色约定：
          - 新增文字 → 绿色背景（结果侧）
          - 删除文字 → 红色背景 + 删除线（原文侧）
          - 修改文字 → 黄色背景（两侧皆标）
        """
        self.orig_diff_edit.clear()
        orig_cursor = self.orig_diff_edit.textCursor()

        self.result_diff_edit.clear()
        res_cursor = self.result_diff_edit.textCursor()

        fmt_normal = QTextCharFormat()
        fmt_normal.setForeground(QColor('#000000'))

        fmt_add = QTextCharFormat()
        fmt_add.setBackground(QColor('#c8e6c9'))  # 浅绿 — 新增

        fmt_delete = QTextCharFormat()
        fmt_delete.setBackground(QColor('#ffcdd2'))  # 浅红 — 删除
        fmt_delete.setFontStrikeOut(True)

        fmt_replace = QTextCharFormat()
        fmt_replace.setBackground(QColor('#fff9c4'))  # 浅黄 — 修改

        for tag, i1, i2, j1, j2 in opcodes:
            # ── 原文侧 ──
            if tag != 'insert':
                orig_text = original[i1:i2]
                if orig_text:
                    if tag == 'equal':
                        f = fmt_normal
                    elif tag == 'delete':
                        f = fmt_delete
                    elif tag == 'replace':
                        f = fmt_replace
                    else:
                        f = fmt_normal
                    orig_cursor.insertText(orig_text, f)

            # ── 结果侧 ──
            if tag != 'delete':
                res_text = processed[j1:j2]
                if res_text:
                    if tag == 'equal':
                        f = fmt_normal
                    elif tag == 'insert':
                        f = fmt_add
                    elif tag == 'replace':
                        f = fmt_replace
                    else:
                        f = fmt_normal
                    res_cursor.insertText(res_text, f)

    # ── 视图更新 ────────────────────────────────────────

    def _update_file_labels(self):
        """更新顶部文件名标签"""
        if self._file_name:
            self.original_name_label.setText(f'原文: {self._file_name}')
            self.result_name_label.setText(f'结果: {self._file_name}')
        else:
            self.original_name_label.setText('原文: ')
            self.result_name_label.setText('结果: ')

    def _update_single_views(self):
        """更新原文/结果单独标签页"""
        self.original_edit.setPlainText(self._original_text)
        self.result_edit.setPlainText(self._processed_text)

    def _update_stats(self):
        """更新底部统计信息"""
        orig_chars = len(self._original_text)
        orig_words = len(self._original_text.split()) if self._original_text.strip() else 0
        proc_chars = len(self._processed_text)
        proc_words = len(self._processed_text.split()) if self._processed_text.strip() else 0

        if self._process_time > 0:
            time_str = f'{self._process_time:.0f} ms'
        else:
            time_str = '--'

        self.stats_label.setText(
            f'原文: {orig_words} 词 / {orig_chars} 字  |  '
            f'结果: {proc_words} 词 / {proc_chars} 字  |  '
            f'耗时: {time_str}'
        )

    def _update_export_buttons(self):
        """更新导出按钮启用状态"""
        has_content = bool(self._processed_text.strip())
        self.export_txt_btn.setEnabled(has_content)
        self.export_md_btn.setEnabled(has_content)
        self.export_docx_btn.setEnabled(has_content)
        self.copy_btn.setEnabled(has_content)

    def _update_all(self):
        """统一更新所有视图和状态"""
        self._update_file_labels()
        self._show_compare_diff()
        self._update_single_views()
        self._update_stats()
        self._update_export_buttons()

    def _show_compare_diff(self):
        """在对比视图中显示差异高亮"""
        if not self._original_text and not self._processed_text:
            self.orig_diff_edit.clear()
            self.result_diff_edit.clear()
            return

        if not self._original_text:
            # 仅有结果
            self.orig_diff_edit.clear()
            self.result_diff_edit.setPlainText(self._processed_text)
            # 结果全绿（全部是新增内容）
            opcodes = self._compute_char_diff('', self._processed_text)
            self._apply_diff_highlight('', self._processed_text, opcodes)
            return

        if not self._processed_text:
            # 仅有原文
            self.orig_diff_edit.setPlainText(self._original_text)
            self.result_diff_edit.clear()
            return

        # 两者都有 → 正常 diff
        opcodes = self._compute_char_diff(self._original_text, self._processed_text)
        self._apply_diff_highlight(self._original_text, self._processed_text, opcodes)

    # ── 公共接口（保持向后兼容） ─────────────────────────

    def show_original(self, text: str, file_name: str = ''):
        """显示原文内容"""
        self._original_text = text
        if file_name:
            self._file_name = file_name
        self.tab_widget.setCurrentIndex(0)
        self._update_all()

    def show_result(self, text: str):
        """显示处理结果"""
        self._processed_text = text
        self.tab_widget.setCurrentIndex(0)
        self._update_all()

    def show_diff_highlight(self, original: str, processed: str):
        """显示带差异高亮的对比视图"""
        self._original_text = original
        self._processed_text = processed
        self.tab_widget.setCurrentIndex(0)
        self._update_all()

    def set_process_time(self, ms: float):
        """设置处理耗时（毫秒）"""
        self._process_time = ms
        self._update_stats()

    def clear_all(self):
        """清空所有内容"""
        self._original_text = ''
        self._processed_text = ''
        self._file_name = ''
        self._process_time = 0.0
        self._update_all()

    # ── 导出操作 ────────────────────────────────────────

    def _copy_result(self):
        """复制结果到剪贴板"""
        text = self.result_edit.toPlainText()
        if not text:
            text = self._processed_text
        if text:
            from PyQt5.QtWidgets import QApplication
            QApplication.clipboard().setText(text)

    def _export_result(self, fmt: str = 'txt'):
        """导出结果到文件，支持 txt / md / docx

        Args:
            fmt: 'txt' / 'md' / 'docx'
        """
        text = self._processed_text
        if not text:
            text = self.result_edit.toPlainText()
            if not text:
                return

        filter_map = {
            'txt': '文本文件 (*.txt)',
            'md': 'Markdown 文件 (*.md)',
            'docx': 'Word 文档 (*.docx)',
        }

        default_name = f'result.{fmt}'
        if self._file_name:
            default_name = Path(self._file_name).stem + f'_processed.{fmt}'

        path, _ = QFileDialog.getSaveFileName(
            self, f'导出为 {fmt.upper()}', str(default_name),
            filter_map.get(fmt, '所有文件 (*.*)')
        )
        if path:
            try:
                if fmt == 'docx':
                    self._export_as_docx(path)
                else:
                    Path(path).write_text(text, encoding='utf-8')
                QMessageBox.information(self, '导出成功', f'已保存到:\n{path}')
            except Exception as e:
                QMessageBox.critical(self, '导出失败', str(e))

    def _export_as_docx(self, path: str):
        """导出为 DOCX，保留基本段落格式"""
        try:
            from docx import Document as DocxDoc
            from docx.shared import Pt
        except ImportError:
            raise ImportError('请安装 python-docx: pip install python-docx')

        text = self._processed_text
        if not text:
            text = self.result_edit.toPlainText()

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
