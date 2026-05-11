"""统一预览面板 — 支持文本和文档两种预览模式

在 PreviewTab 中提供两种模式：
  1. 📄 文档模式（推荐）— 通过 DocPreviewWidget 像 Word 一样显示 .docx
  2. 📝 文本模式 — 通过 PreviewWidget 进行传统左右对比 + 差异高亮

接口兼容旧的 PreviewWidget，可以无缝替换。
"""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QPushButton, QLabel, QButtonGroup, QFrame,
)
from PyQt5.QtCore import Qt, pyqtSignal

from app.ui_preview import PreviewWidget
from app.doc_preview import DocPreviewWidget, wrap_html

logger = logging.getLogger(__name__)


class PreviewPanel(QWidget):
    """主预览面板，支持文本和文档两种模式。

    接口兼容 PreviewWidget，可直接替换 ui_main.py 中的 self.preview。

    信号:
        mode_changed: 预览模式变更信号 (mode: str) — "text" 或 "document"
    """

    mode_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_mode = "document"  # "text" | "document"
        self._original_text = ""
        self._processed_text = ""
        self._file_name = ""
        self._original_file: Optional[Path] = None
        self._result_file: Optional[Path] = None
        self._process_time = 0.0

        self._build_ui()

    # ── UI 构建 ─────────────────────────────────────────────

    def _build_ui(self):
        """构建完整 UI。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._build_mode_switch(layout)
        self._build_stacked_views(layout)

    def _build_mode_switch(self, layout):
        """构建模式切换栏。"""
        bar = QFrame()
        bar.setStyleSheet(
            "QFrame { background: #f8f9fa; border-bottom: 1px solid #e0e0e0; }"
        )
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(8, 4, 8, 4)
        bar_layout.setSpacing(4)

        label = QLabel("预览模式:")
        label.setStyleSheet("font-size: 12px; color: #666; font-weight: 500;")
        bar_layout.addWidget(label)

        # 按钮组（互斥）
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)

        self.btn_doc_mode = QPushButton("📄 文档模式")
        self.btn_doc_mode.setCheckable(True)
        self.btn_doc_mode.setChecked(True)
        self.btn_doc_mode.setToolTip("像 Word 一样显示文档")
        self.btn_doc_mode.setCursor(Qt.PointingHandCursor)
        self.btn_doc_mode.clicked.connect(lambda: self._switch_mode("document"))
        self.btn_doc_mode.setStyleSheet(self._mode_btn_style(True))
        self.mode_group.addButton(self.btn_doc_mode)
        bar_layout.addWidget(self.btn_doc_mode)

        self.btn_text_mode = QPushButton("📝 文本模式")
        self.btn_text_mode.setCheckable(True)
        self.btn_text_mode.setToolTip("传统左右对比 + 差异高亮")
        self.btn_text_mode.setCursor(Qt.PointingHandCursor)
        self.btn_text_mode.clicked.connect(lambda: self._switch_mode("text"))
        self.btn_text_mode.setStyleSheet(self._mode_btn_style(False))
        self.mode_group.addButton(self.btn_text_mode)
        bar_layout.addWidget(self.btn_text_mode)

        bar_layout.addStretch()
        layout.addWidget(bar)

    def _build_stacked_views(self, layout):
        """构建堆叠视图。"""
        self.stack = QStackedWidget()

        # 第 0 页：文档模式
        self.doc_preview = DocPreviewWidget()
        self.stack.addWidget(self.doc_preview)

        # 第 1 页：文本模式
        self.text_preview = PreviewWidget()
        self.stack.addWidget(self.text_preview)

        layout.addWidget(self.stack, 1)

    @staticmethod
    def _mode_btn_style(active: bool = False) -> str:
        if active:
            return (
                "QPushButton {"
                "  background: #4a90d9; color: white;"
                "  border: 1px solid #4a90d9; border-radius: 4px;"
                "  padding: 4px 12px; font-size: 12px;"
                "}"
            )
        return (
            "QPushButton {"
            "  background: transparent; color: #555;"
            "  border: 1px solid #ddd; border-radius: 4px;"
            "  padding: 4px 12px; font-size: 12px;"
            "}"
            "QPushButton:hover {"
            "  background: #e8e8e8; border-color: #aaa;"
            "}"
        )

    # ── 模式切换 ────────────────────────────────────────────

    def _switch_mode(self, mode: str):
        """切换预览模式。

        Args:
            mode: "document" 或 "text"
        """
        if mode == self._current_mode:
            return

        self._current_mode = mode
        is_doc = mode == "document"

        # 更新按钮样式
        self.btn_doc_mode.setStyleSheet(self._mode_btn_style(is_doc))
        self.btn_text_mode.setStyleSheet(self._mode_btn_style(not is_doc))

        # 切换视图
        self.stack.setCurrentIndex(0 if is_doc else 1)

        # 同步内容到新模式
        if is_doc:
            self._sync_to_doc_mode()
        else:
            self._sync_to_text_mode()

        self.mode_changed.emit(mode)

    def _sync_to_doc_mode(self):
        """将当前内容同步到文档模式。"""
        if self._result_file and self._result_file.exists():
            # 优先加载 .docx 文件
            if self._original_file and self._original_file.exists():
                self.doc_preview.load_compare(
                    self._original_file, self._result_file
                )
            else:
                self.doc_preview.load_docx(self._result_file)
        elif self._original_file and self._original_file.exists():
            self.doc_preview.load_docx(self._original_file)
        elif self._processed_text:
            # 纯文本渲染为 HTML
            html = wrap_html(f"<pre>{self._processed_text}</pre>")
            self.doc_preview.load_html(html)
        elif self._original_text:
            html = wrap_html(f"<pre>{self._original_text}</pre>")
            self.doc_preview.load_html(html)

    def _sync_to_text_mode(self):
        """将当前内容同步到文本模式。"""
        self.text_preview.show_diff_highlight(
            self._original_text, self._processed_text
        )

    # ── 公开接口（兼容 PreviewWidget）───────────────────────

    def show_original(self, text: str, file_name: str = ""):
        """显示原文内容。

        Args:
            text: 原文文本
            file_name: 文件名
        """
        self._original_text = text
        if file_name:
            self._file_name = file_name
        self._original_file = None

        if self._current_mode == "document":
            # 尝试找同名的 .docx 文件
            self._try_find_docx()
            if self._original_file and self._original_file.exists():
                self.doc_preview.load_docx(self._original_file)
            else:
                # 没有 .docx 文件，用纯文本渲染
                html = wrap_html(f"<pre>{text}</pre>")
                self.doc_preview.load_html(html)
        else:
            self.text_preview.show_original(text, file_name)

    def show_result(self, text: str):
        """显示处理结果。

        Args:
            text: 处理后的文本
        """
        self._processed_text = text

        if self._current_mode == "document":
            if self._result_file and self._result_file.exists():
                if self._original_file and self._original_file.exists():
                    self.doc_preview.load_compare(
                        self._original_file, self._result_file
                    )
                else:
                    self.doc_preview.load_docx(self._result_file)
            else:
                html = wrap_html(f"<pre>{text}</pre>")
                self.doc_preview.load_html(html)
        else:
            self.text_preview.show_result(text)

    def show_diff_highlight(self, original: str, processed: str):
        """显示带差异高亮的对比视图。

        Args:
            original: 原文
            processed: 处理结果
        """
        self._original_text = original
        self._processed_text = processed

        if self._current_mode == "document":
            self._sync_to_doc_mode()
        else:
            self.text_preview.show_diff_highlight(original, processed)

    def set_content(
        self,
        original_text: str,
        result_text: str,
        original_file: Optional[str | Path] = None,
        result_file: Optional[str | Path] = None,
    ):
        """设置预览内容（推荐接口）。

        如果有 .docx 文件路径，文档模式会优先加载 docx 渲染。
        否则回退到纯文本显示。

        Args:
            original_text: 原文文本
            result_text: 处理结果文本
            original_file: 原文 .docx 路径（可选）
            result_file: 结果 .docx 路径（可选）
        """
        self._original_text = original_text
        self._processed_text = result_text
        if original_file:
            self._original_file = Path(original_file)
        if result_file:
            self._result_file = Path(result_file)

        if self._current_mode == "document":
            self._sync_to_doc_mode()
        else:
            self._sync_to_text_mode()

    def set_process_time(self, ms: float):
        """设置处理耗时（毫秒）。

        Args:
            ms: 毫秒数
        """
        self._process_time = ms
        self.text_preview.set_process_time(ms)

    def clear_all(self):
        """清空所有内容。"""
        self._original_text = ""
        self._processed_text = ""
        self._file_name = ""
        self._original_file = None
        self._result_file = None

        self.doc_preview.load_html("")
        self.text_preview.clear_all()

    # ── 辅助方法 ────────────────────────────────────────────

    def _try_find_docx(self):
        """根据 _file_name 尝试找到对应的 .docx 文件。

        查找顺序：
          1. self._file_name 自身（可能是完整路径）
          2. 同目录下加 .docx 后缀
          3. outputs/ 子目录下（批处理输出目录）
          4. 用户 home 的 .ai-doc-processor/output/ 目录
        """
        if not self._file_name:
            return

        candidates = []
        file_name = Path(self._file_name)

        # 1. 自身（完整路径）
        candidates.append(file_name)

        # 2. 同目录下加 .docx 后缀
        if file_name.suffix.lower() != ".docx":
            candidates.append(file_name.with_suffix(".docx"))
        else:
            candidates.append(file_name)

        # 3. outputs/ 子目录
        candidates.append(Path("outputs") / file_name.name)
        candidates.append(Path("outputs") / (file_name.stem + ".docx"))

        # 4. 批处理输出默认目录
        output_dir = Path.home() / ".ai-doc-processor" / "output"
        candidates.append(output_dir / file_name.name)
        candidates.append(output_dir / (file_name.stem + ".docx"))

        for c in candidates:
            resolved = c.resolve() if c.exists() else c
            if resolved.exists():
                self._original_file = resolved
                return

    # ── 适配属性访问（兼容旧代码）───────────────────────────

    @property
    def original_edit(self):
        """兼容旧代码对 self.preview.original_edit 的访问。"""
        return self.text_preview.original_edit

    @property
    def result_edit(self):
        """兼容旧代码对 self.preview.result_edit 的访问。"""
        return self.text_preview.result_edit

    @property
    def orig_diff_edit(self):
        return self.text_preview.orig_diff_edit

    @property
    def result_diff_edit(self):
        return self.text_preview.result_diff_edit
