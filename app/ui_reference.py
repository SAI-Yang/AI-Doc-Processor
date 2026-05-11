"""参考文档管理UI

用户可以添加、查看、删除参考文档，显示分析结果摘要。
纯规则分析，在添加文件时自动进行。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFrame, QFileDialog, QMessageBox,
    QScrollArea, QSizePolicy, QApplication,
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import (
    QFont, QColor, QDragEnterEvent, QDropEvent, QPainter, QPen, QBrush,
)

from app.reference_analyzer import ReferenceAnalyzer

logger = logging.getLogger(__name__)

# ── 文件类型图标 ──────────────────────────────────────────
_FILE_ICONS = {
    ".docx": "📄",
    ".pdf": "📕",
    ".txt": "📃",
    ".md": "📝",
}


class ReferenceItem(QFrame):
    """参考文档列表项卡片

    显示文件名、类型图标、分析标签（章节数/风格/语言）。
    可点击选中，带删除按钮。
    """

    remove_requested = pyqtSignal(object)  # self

    def __init__(self, file_path: str, analysis: dict, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.analysis = analysis
        self._selected = False
        self._build_ui()

    def _build_ui(self):
        self.setFixedHeight(54)
        self.setCursor(Qt.PointingHandCursor)
        self.setFrameShape(QFrame.StyledPanel)
        self._update_style()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        # 文件类型图标
        path = Path(self.file_path)
        icon = _FILE_ICONS.get(path.suffix.lower(), "📄")
        icon_label = QLabel(icon)
        icon_label.setFont(QFont("Segoe UI", 20))
        icon_label.setFixedWidth(30)
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        # 右侧文字区
        text_layout = QVBoxLayout()
        text_layout.setSpacing(1)

        # 文件名
        name_label = QLabel(path.name)
        name_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #1f2328;")
        name_label.setWordWrap(False)
        text_layout.addWidget(name_label)

        # 分析标签行
        tags = self._build_tags()
        tag_label = QLabel(" · ".join(tags))
        tag_label.setStyleSheet("font-size: 11px; color: #656d76;")
        text_layout.addWidget(tag_label)

        layout.addLayout(text_layout, 1)

        # 删除按钮
        del_btn = QPushButton("×")
        del_btn.setFixedSize(22, 22)
        del_btn.setToolTip("移除此参考文档")
        del_btn.setStyleSheet("""
            QPushButton {
                font-size: 15px; font-weight: bold; color: #656d76;
                background: transparent; border: none; border-radius: 11px;
            }
            QPushButton:hover { background-color: #f85149; color: white; }
        """)
        del_btn.clicked.connect(lambda: self.remove_requested.emit(self))
        layout.addWidget(del_btn)

    def _build_tags(self) -> list[str]:
        """根据分析结果构建标签列表"""
        tags: list[str] = []
        analysis = self.analysis

        hc = analysis.get("heading_count", 0)
        if hc > 0:
            tags.append(f"{hc} 章")

        style = analysis.get("style", {})
        formality_map = {"formal": "正式", "casual": "随性", "technical": "技术"}
        tags.append(formality_map.get(style.get("formality", ""), "未知") + "风格")

        lang = analysis.get("language", "zh")
        tags.append("中文" if lang == "zh" else "英文")

        if analysis.get("table_count", 0) > 0:
            tags.append(f"{analysis['table_count']} 表")
        if analysis.get("image_count", 0) > 0:
            tags.append(f"{analysis['image_count']} 图")

        return tags

    def _update_style(self):
        """刷新卡片样式"""
        if self._selected:
            self.setStyleSheet("""
                ReferenceItem {
                    background-color: #ddf4ff;
                    border: 2px solid #0969da;
                    border-radius: 6px;
                }
            """)
        else:
            self.setStyleSheet("""
                ReferenceItem {
                    background-color: #f6f8fa;
                    border: 1px solid #d0d7de;
                    border-radius: 6px;
                }
                ReferenceItem:hover {
                    background-color: #eef1f5;
                    border-color: #8b949e;
                }
            """)

    def set_selected(self, sel: bool):
        self._selected = sel
        self._update_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 通知父级选中
            parent = self.parent()
            while parent and not hasattr(parent, "select_item"):
                parent = parent.parent()
            if parent:
                parent.select_item(self)
        super().mousePressEvent(event)


class ReferenceManager(QWidget):
    """参考文档管理器 UI

    布局：
    +-------------------------------------------+
    | 📎 参考文档                      [+ 添加]  |
    +-------------------------------------------+
    | [ref1.docx ✓] 技术报告 · 3章 · 正式风格   |
    | [ref2.pdf  ✓]  合同模板 · 5节 · 法律风格   |
    +-------------------------------------------+
    | 分析结果（选中文档时显示）                 |
    | 标题：XXX                                  |
    | 结构：3章 12节                             |
    | 风格：正式·客观                            |
    | 关键词：机器学习、数据分析...               |
    +-------------------------------------------+
    """

    reference_added = pyqtSignal(str)  # file_path
    reference_removed = pyqtSignal(str)  # file_path
    reference_selected = pyqtSignal(dict)  # analysis

    def __init__(self, parent=None):
        super().__init__(parent)
        self._analyzer = ReferenceAnalyzer()
        self._items: list[ReferenceItem] = []
        self._selected_item: Optional[ReferenceItem] = None
        self._build_ui()
        self.setAcceptDrops(True)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # ── 标题行 ──────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(6)

        title = QLabel("📎 参考文档")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1f2328;")
        header.addWidget(title)

        # 参考计数
        self.count_label = QLabel("0")
        self.count_label.setStyleSheet(
            "font-size: 11px; color: #656d76; background: #eef1f5;"
            " border-radius: 8px; padding: 0 6px;"
        )
        header.addWidget(self.count_label)

        header.addStretch()

        self.add_btn = QPushButton("+ 添加")
        self.add_btn.setToolTip("添加参考文档 (.docx .pdf .txt .md)")
        self.add_btn.setStyleSheet("""
            QPushButton {
                font-size: 12px; padding: 4px 12px;
                background-color: #0969da; color: white;
                border: none; border-radius: 4px;
            }
            QPushButton:hover { background-color: #0860ca; }
        """)
        self.add_btn.clicked.connect(self._on_add_clicked)
        header.addWidget(self.add_btn)

        layout.addLayout(header)

        # ── 参考文档列表（滚动区域） ──────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMinimumHeight(60)
        scroll.setMaximumHeight(220)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: 1px dashed #d0d7de;
                border-radius: 6px;
            }
            QScrollArea:empty { background: #f6f8fa; }
        """)

        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(6, 6, 6, 6)
        self.list_layout.setSpacing(4)
        self.list_layout.addStretch()

        # 拖拽提示（当列表为空时显示）
        self.drop_hint = QLabel("拖拽文件到此处添加参考文档")
        self.drop_hint.setAlignment(Qt.AlignCenter)
        self.drop_hint.setStyleSheet("color: #8b949e; font-size: 12px; padding: 16px;")
        self.drop_hint.setFixedHeight(48)
        self.list_layout.insertWidget(0, self.drop_hint)

        scroll.setWidget(self.list_container)
        layout.addWidget(scroll)

        # ── 选中项分析详情 ────────────────────────────
        self.detail_panel = QFrame()
        self.detail_panel.setStyleSheet("""
            QFrame {
                background-color: #f6f8fa;
                border: 1px solid #d0d7de;
                border-radius: 6px;
            }
        """)
        self.detail_panel.setVisible(False)
        detail_layout = QVBoxLayout(self.detail_panel)
        detail_layout.setContentsMargins(10, 8, 10, 8)
        detail_layout.setSpacing(3)

        self.detail_title = QLabel("")
        self.detail_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #0969da;")
        detail_layout.addWidget(self.detail_title)

        self.detail_info = QLabel("")
        self.detail_info.setStyleSheet("font-size: 11px; color: #1f2328; line-height: 1.5;")
        self.detail_info.setWordWrap(True)
        detail_layout.addWidget(self.detail_info)

        layout.addWidget(self.detail_panel)

        self._update_count()

    # ── 内部方法 ──────────────────────────────────────────

    def _update_count(self):
        """更新参考文档计数"""
        count = len(self._items)
        self.count_label.setText(str(count))
        self.drop_hint.setVisible(count == 0)

    def _on_add_clicked(self):
        """添加文件按钮回调"""
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择参考文档", "",
            "所有支持的文件 (*.docx *.pdf *.txt *.md);;"
            "Word 文档 (*.docx);;PDF 文档 (*.pdf);;"
            "文本文件 (*.txt);;Markdown (*.md);;所有文件 (*.*)"
        )
        for p in paths:
            self._add_reference(p)

    def _add_reference(self, file_path: str):
        """添加并分析单个参考文档"""
        path = Path(file_path)
        if not path.exists():
            return

        # 去重检查
        for item in self._items:
            if Path(item.file_path).resolve() == path.resolve():
                QMessageBox.information(self, "提示", f"文件已添加: {path.name}")
                return

        # 分析
        try:
            analysis = self._analyzer.analyze(file_path)
        except Exception as exc:
            logger.warning("参考文档分析失败: %s", exc)
            QMessageBox.warning(
                self, "分析失败",
                f"无法分析参考文档: {path.name}\n\n{exc}"
            )
            return

        # 创建卡片
        item = ReferenceItem(file_path, analysis)
        item.remove_requested.connect(self._remove_item)

        # 插入到 stretch 之前
        self.list_layout.insertWidget(self.list_layout.count() - 1, item)
        self._items.append(item)
        self._update_count()
        self.reference_added.emit(file_path)

        # 默认选中第一个
        if len(self._items) == 1:
            self.select_item(item)

    def _remove_item(self, item: ReferenceItem):
        """移除参考文档"""
        # 从布局移除
        self.list_layout.removeWidget(item)

        if item in self._items:
            self._items.remove(item)

        if self._selected_item is item:
            self._selected_item = None
            self.detail_panel.setVisible(False)

        item.deleteLater()
        self._update_count()
        self.reference_removed.emit(item.file_path)

    def select_item(self, item: ReferenceItem):
        """选中某个参考文档，显示分析详情"""
        # 取消旧选中
        if self._selected_item and self._selected_item is not item:
            self._selected_item.set_selected(False)

        self._selected_item = item
        item.set_selected(True)

        # 更新详情面板
        analysis = item.analysis
        self.detail_title.setText(Path(item.file_path).name)
        self.detail_panel.setVisible(True)

        lines: list[str] = []

        # 语言
        lang = "中文" if analysis.get("language") == "zh" else "英文"
        lines.append(f"语言: {lang}")

        # 字数 + 段落
        lines.append(f"字数: {analysis.get('word_count', 0)}  |  段落: {analysis.get('paragraph_count', 0)}")

        # 结构
        hc = analysis.get("heading_count", 0)
        if hc > 0:
            lines.append(f"章节: {hc} 个标题")
            structure = analysis.get("structure", [])
            if structure:
                titles = []
                for s in structure[:5]:
                    t = s.get("text", "")
                    if len(t) > 28:
                        t = t[:28] + "..."
                    titles.append(t)
                if len(structure) > 5:
                    titles.append("...")
                lines.append("结构: " + " → ".join(titles))

        # 表格/图片
        extras = []
        if analysis.get("table_count", 0) > 0:
            extras.append(f"表格 {analysis['table_count']} 个")
        if analysis.get("image_count", 0) > 0:
            extras.append(f"图片 {analysis['image_count']} 张")
        if extras:
            lines.append("包含: " + "、".join(extras))

        # 风格
        style = analysis.get("style", {})
        formality_map = {"formal": "正式", "casual": "随性"}
        tone_map = {"objective": "客观", "subjective": "主观", "persuasive": "说服性"}
        lines.append(
            f"风格: {formality_map.get(style.get('formality', ''), '未知')}"
            f" · {tone_map.get(style.get('tone', ''), '未知')}"
        )
        if style.get("font"):
            lines.append(f"字体: {style['font']} {style.get('font_size', '')}")

        # 关键词
        topics = analysis.get("key_topics", [])
        if topics:
            lines.append(f"关键词: {'、'.join(topics[:8])}")

        self.detail_info.setText("\n".join(lines))
        self.reference_selected.emit(analysis)

    # ── 拖拽支持 ──────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        added = 0
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path:
                ext = Path(file_path).suffix.lower()
                if ext in (".docx", ".pdf", ".txt", ".md"):
                    self._add_reference(file_path)
                    added += 1
        event.acceptProposedAction()
        if added > 0:
            logger.info("拖拽添加了 %d 个参考文档", added)

    # ── 对外接口 ──────────────────────────────────────────

    def get_reference_texts(self) -> list[str]:
        """获取所有参考文档的文本内容

        Returns:
            每个文档的文本内容列表
        """
        texts: list[str] = []
        for item in self._items:
            try:
                text = _extract_simple_text(Path(item.file_path))
                texts.append(text)
            except Exception as exc:
                logger.warning("读取参考文档文本失败: %s", exc)
                texts.append("")
        return texts

    def get_reference_analysis(self) -> list[dict]:
        """获取所有参考文档的分析结果

        Returns:
            分析结果字典列表
        """
        return [item.analysis for item in self._items]

    def add_reference(self, file_path: str):
        """添加参考文档（供外部调用）"""
        self._add_reference(file_path)

    def clear(self):
        """清空所有参考文档"""
        items_copy = list(self._items)
        for item in items_copy:
            self._remove_item(item)

    def count(self) -> int:
        """返回参考文档数量"""
        return len(self._items)


def _extract_simple_text(file_path: Path) -> str:
    """从文件提取纯文本（简化版，不依赖 app.document）

    Args:
        file_path: 文件路径

    Returns:
        纯文本内容
    """
    suffix = file_path.suffix.lower()
    if suffix == ".docx":
        from docx import Document as DocxDoc
        doc = DocxDoc(str(file_path))
        return "\n".join(p.text for p in doc.paragraphs)
    elif suffix == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(str(file_path)) as pdf:
                return "\n".join(page.extract_text() or "" for page in pdf.pages)
        except ImportError:
            pass
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(str(file_path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except ImportError:
            return ""
    else:
        for enc in ("utf-8", "gbk", "latin-1"):
            try:
                return file_path.read_text(encoding=enc)
            except (UnicodeDecodeError, LookupError):
                continue
        return file_path.read_bytes().decode("utf-8", errors="replace")
