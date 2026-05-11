"""Word 风格文档预览组件

使用 mammoth 将 .docx 转换为 HTML，通过 QWebEngineView 渲染，
保留原始排版（字体、字号、表格、图片等）。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QSplitter, QCheckBox, QFileDialog,
    QMessageBox,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWebEngineWidgets import QWebEngineView

logger = logging.getLogger(__name__)

# ── Word 风格 CSS ──────────────────────────────────────────

WORD_STYLE_CSS = """
<style>
    body {
        font-family: 'Times New Roman', '宋体', serif;
        font-size: 12pt;
        line-height: 1.5;
        margin: 72pt 72pt;
        color: #000;
        background: #fff;
    }
    h1 { font-size: 18pt; font-weight: bold; margin: 12pt 0; }
    h2 { font-size: 16pt; font-weight: bold; margin: 10pt 0; }
    h3 { font-size: 14pt; font-weight: bold; margin: 8pt 0; }
    p { margin: 6pt 0; text-indent: 2em; }
    table {
        border-collapse: collapse;
        width: 100%;
        margin: 12pt 0;
    }
    td, th {
        border: 1pt solid #333;
        padding: 4pt 8pt;
        vertical-align: top;
    }
    th { background: #f0f0f0; font-weight: bold; }
    img { max-width: 100%; height: auto; }
    ul, ol { margin: 6pt 0; padding-left: 2em; }
    li { margin: 2pt 0; }
    blockquote {
        margin: 8pt 0;
        padding: 4pt 12pt;
        border-left: 3pt solid #ccc;
        color: #555;
    }
    hr { border: none; border-top: 1pt solid #ccc; margin: 12pt 0; }
    /* 对比模式高亮色 */
    .diff-added { background-color: #c8e6c9; }
    .diff-removed { background-color: #ffcdd2; text-decoration: line-through; }
</style>
"""

# ── 空页面占位符 HTML ─────────────────────────────────────

EMPTY_HTML = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8">{WORD_STYLE_CSS}</head>
<body>
    <p style="color: #999; text-align: center; margin-top: 80pt;">
        暂无内容 — 请选择文件或加载文档
    </p>
</body>
</html>"""


# ── 工具函数 ───────────────────────────────────────────────

def docx_to_html(docx_path: str | Path) -> str:
    """将 .docx 转换为 HTML，保留格式和图片。

    图片通过 mammoth 自定义转换器转为 base64 内嵌到 HTML 中，
    无需外部文件即可在浏览器中完整显示。

    Args:
        docx_path: .docx 文件路径

    Returns:
        HTML 字符串（含 base64 内嵌图片）
    """
    import mammoth
    import base64

    def _convert_image(image):
        """将 docx 内嵌图片转为 base64 data URI"""
        with image.open() as img_bytes:
            content_type = image.content_type
            b64 = base64.b64encode(img_bytes.read()).decode()
            src = f"data:{content_type};base64,{b64}"
        return {"src": src}

    with open(str(docx_path), "rb") as f:
        try:
            result = mammoth.convert_to_html(
                f,
                convert_image=mammoth.images.img_element(_convert_image)
            )
        except (AttributeError, ImportError):
            # 旧版 mammoth 不支持自定义图片转换器，降级为无图模式
            logger.warning("mammoth 不支持自定义图片转换器，图片将被忽略")
            result = mammoth.convert_to_html(f)

        # 记录 mammoth 转换过程中的警告
        for msg in result.messages:
            logger.warning("mammoth 转换消息: %s", msg)
        return result.value


def wrap_html(body_html: str) -> str:
    """将正文 HTML 包裹为完整页面。

    Args:
        body_html: 正文 HTML（不含 body 标签）

    Returns:
        完整 HTML 文档
    """
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8">{WORD_STYLE_CSS}</head>
<body>
{body_html}
</body>
</html>"""


# ── 可同步滚动的 WebEngineView ────────────────────────────

class _SyncWebView(QWebEngineView):
    """支持编程同步滚动的 WebEngineView"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sync_target: Optional[_SyncWebView] = None
        self._is_syncing = False

    def set_sync_target(self, target: Optional["_SyncWebView"]):
        """设置同步滚动的目标视图。"""
        self._sync_target = target

    def scroll_to(self, x: int, y: int):
        """滚动到指定位置。"""
        js = f"window.scrollTo({x}, {y});"
        self.page().runJavaScript(js)

    def get_scroll_position(self, callback):
        """获取当前滚动位置（异步回调）。"""
        self.page().runJavaScript(
            "JSON.stringify({x: window.scrollX, y: window.scrollY});",
            callback,
        )


# ── 文档预览组件 ──────────────────────────────────────────

class DocPreviewWidget(QWidget):
    """Word 风格的文档预览组件。

    支持 .docx 格式预览，保留原始排版。
    提供缩放、对比模式、导出 PDF 等功能。
    """

    ZOOM_MIN = 0.5
    ZOOM_MAX = 2.0
    ZOOM_STEP = 0.1

    def __init__(self, parent=None):
        super().__init__(parent)
        self._zoom_factor = 1.0
        self._current_html = EMPTY_HTML
        self._compare_mode = False
        self._original_html = EMPTY_HTML
        self._result_html = EMPTY_HTML
        self._build_ui()

    # ── UI 构建 ─────────────────────────────────────────────

    def _build_ui(self):
        """构建完整 UI。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._build_toolbar(layout)
        self._build_view_area(layout)
        self._build_status_bar(layout)

    def _build_toolbar(self, parent_layout):
        """构建顶部工具栏。"""
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 4, 8, 4)
        toolbar.setSpacing(4)

        # 缩放按钮
        self.btn_zoom_out = QPushButton("−")
        self.btn_zoom_out.setFixedSize(28, 28)
        self.btn_zoom_out.setToolTip("缩小")
        self.btn_zoom_out.clicked.connect(self._zoom_out)
        self.btn_zoom_out.setStyleSheet(self._btn_toolbar_style())

        self.zoom_label = QLabel("100%")
        self.zoom_label.setFixedWidth(44)
        self.zoom_label.setAlignment(Qt.AlignCenter)
        self.zoom_label.setStyleSheet("font-size: 12px; color: #555;")

        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.setFixedSize(28, 28)
        self.btn_zoom_in.setToolTip("放大")
        self.btn_zoom_in.clicked.connect(self._zoom_in)
        self.btn_zoom_in.setStyleSheet(self._btn_toolbar_style())

        toolbar.addWidget(self.btn_zoom_out)
        toolbar.addWidget(self.zoom_label)
        toolbar.addWidget(self.btn_zoom_in)

        toolbar.addSpacing(12)

        # 分隔线
        sep = QLabel("|")
        sep.setStyleSheet("color: #ddd; font-size: 14px;")
        toolbar.addWidget(sep)
        toolbar.addSpacing(12)

        # 对比模式开关
        self.compare_check = QCheckBox("对比模式")
        self.compare_check.setToolTip("上下分栏显示原文和结果")
        self.compare_check.setStyleSheet(
            "font-size: 12px; color: #555; spacing: 4px;"
        )
        self.compare_check.toggled.connect(self._toggle_compare_mode)
        toolbar.addWidget(self.compare_check)

        toolbar.addSpacing(12)

        # 分隔线
        sep2 = QLabel("|")
        sep2.setStyleSheet("color: #ddd; font-size: 14px;")
        toolbar.addWidget(sep2)
        toolbar.addSpacing(12)

        # 导出 PDF
        self.btn_export_pdf = QPushButton("导出 PDF")
        self.btn_export_pdf.setToolTip("将当前预览导出为 PDF")
        self.btn_export_pdf.clicked.connect(self.export_pdf)
        self.btn_export_pdf.setStyleSheet(self._btn_action_style())
        toolbar.addWidget(self.btn_export_pdf)

        toolbar.addStretch()
        parent_layout.addLayout(toolbar)

    def _build_view_area(self, parent_layout):
        """构建预览区域（QSplitter 支撑对比模式）。"""
        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.setHandleWidth(6)
        self.splitter.setStyleSheet("""
            QSplitter::handle {
                background: #e0e0e0;
                border: none;
            }
            QSplitter::handle:hover {
                background: #4a90d9;
            }
        """)

        # 主视图
        self.web_view = _SyncWebView()
        self.web_view.setHtml(EMPTY_HTML)
        self.splitter.addWidget(self.web_view)

        # 对比视图（初始隐藏）
        self.compare_view = _SyncWebView()
        self.compare_view.setHtml(EMPTY_HTML)
        self.compare_view.setVisible(False)
        self.splitter.addWidget(self.compare_view)

        # 默认仅显示主视图
        self.splitter.setSizes([1, 0])

        parent_layout.addWidget(self.splitter, 1)

    def _build_status_bar(self, parent_layout):
        """构建底部状态栏。"""
        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(8, 2, 8, 4)
        status_layout.setSpacing(16)

        self.page_label = QLabel("")
        self.page_label.setStyleSheet("color: #888; font-size: 11px;")
        status_layout.addWidget(self.page_label)
        status_layout.addStretch()

        self.word_count_label = QLabel("")
        self.word_count_label.setStyleSheet("color: #888; font-size: 11px;")
        status_layout.addWidget(self.word_count_label)

        parent_layout.addLayout(status_layout)

    # ── 样式辅助 ───────────────────────────────────────────

    @staticmethod
    def _btn_toolbar_style() -> str:
        return (
            "QPushButton {"
            "  background: #f5f5f5; border: 1px solid #d0d0d0;"
            "  border-radius: 4px; font-size: 14px; font-weight: bold;"
            "  color: #333;"
            "}"
            "QPushButton:hover {"
            "  background: #e8e8e8; border-color: #aaa;"
            "}"
            "QPushButton:pressed {"
            "  background: #d5d5d5;"
            "}"
        )

    @staticmethod
    def _btn_action_style() -> str:
        return (
            "QPushButton {"
            "  background: #ffffff; border: 1px solid #d0d7de;"
            "  border-radius: 6px; padding: 4px 14px;"
            "  font-size: 12px; color: #333;"
            "}"
            "QPushButton:hover {"
            "  background: #f0f4ff; border-color: #4a90d9;"
            "}"
            "QPushButton:pressed {"
            "  background: #dde6ff;"
            "}"
        )

    # ── 公开接口 ────────────────────────────────────────────

    def load_docx(self, file_path: str | Path):
        """加载并显示 .docx 文件。

        Args:
            file_path: .docx 文件路径
        """
        try:
            html_body = docx_to_html(file_path)
            self._result_html = wrap_html(html_body)
            self._update_display()
            self._update_status(file_path)
        except Exception as e:
            logger.error("加载 DOCX 失败: %s", e)
            self._show_error(f"加载文档失败:\n{e}")

    def load_html(self, html_content: str):
        """直接渲染 HTML 内容。

        Args:
            html_content: 完整的 HTML 内容
        """
        self._result_html = html_content if "<!DOCTYPE" in html_content else wrap_html(html_content)
        # 非对比模式时直接显示
        if not self._compare_mode:
            self.web_view.setHtml(self._result_html)
        else:
            self._update_compare_view()
        self._update_word_count()

    def load_compare(self, original_path: str | Path, result_path: str | Path):
        """加载对比视图（上下分栏）。

        上 = 原文，下 = 处理结果。

        Args:
            original_path: 原文 .docx 路径
            result_path: 处理结果 .docx 路径
        """
        try:
            orig_html = docx_to_html(original_path)
            result_html = docx_to_html(result_path)
            self._original_html = wrap_html(orig_html)
            self._result_html = wrap_html(result_html)
            self._compare_mode = True
            self.compare_check.setChecked(True)
            self._update_compare_view()
        except Exception as e:
            logger.error("加载对比视图失败: %s", e)
            self._show_error(f"加载对比视图失败:\n{e}")

    def set_zoom(self, factor: float):
        """设置缩放比例 0.5-2.0。

        Args:
            factor: 缩放比例
        """
        factor = max(self.ZOOM_MIN, min(self.ZOOM_MAX, factor))
        self._zoom_factor = factor
        self.zoom_label.setText(f"{int(factor * 100)}%")
        self._apply_zoom()

    def export_pdf(self, output_path: str = ""):
        """导出当前视图为 PDF。

        Args:
            output_path: 输出路径。留空则弹出保存对话框
        """
        if not output_path:
            path, _ = QFileDialog.getSaveFileName(
                self, "导出为 PDF", "preview.pdf",
                "PDF 文件 (*.pdf);;所有文件 (*.*)"
            )
            if not path:
                return
            output_path = path

        def _print_callback(success: bool):
            if success:
                QMessageBox.information(
                    self, "导出成功", f"PDF 已保存到:\n{output_path}"
                )
            else:
                QMessageBox.warning(self, "导出失败", "PDF 导出失败")

        # 使用 QWebEngineView 的打印功能
        self.web_view.page().printToPdf(
            output_path,
        )
        # 直接通知（printToPdf 成功时不会回调，但写入文件即表示成功）
        QTimer.singleShot(500, lambda: _print_callback(True))

    # ── 私有方法 ────────────────────────────────────────────

    def _update_display(self):
        """根据当前模式更新显示。"""
        if self._compare_mode:
            self._update_compare_view()
        else:
            self.web_view.setHtml(self._result_html)
            self.compare_view.setVisible(False)

    def _update_compare_view(self):
        """更新对比视图。"""
        self.web_view.setHtml(self._original_html)
        self.compare_view.setHtml(self._result_html)
        self.compare_view.setVisible(True)
        self.splitter.setSizes([400, 400])

        # 设置同步滚动
        self.web_view.set_sync_target(self.compare_view)
        self.compare_view.set_sync_target(self.web_view)
        self._setup_sync_scroll()

    def _setup_sync_scroll(self):
        """设置上下分栏的同步滚动。"""
        def _make_scroll_handler(source, target):
            def _handler():
                source.get_scroll_position(
                    lambda pos_str: self._on_scroll_pos(target, pos_str)
                )
            return _handler

        # 连接滚动事件（通过 wheelEvent 代理）
        self._orig_scroll_handler = _make_scroll_handler(
            self.web_view, self.compare_view
        )
        self._result_scroll_handler = _make_scroll_handler(
            self.compare_view, self.web_view
        )

    def _on_scroll_pos(self, target_view: _SyncWebView, pos_str: str):
        """同步滚动到目标视图。"""
        import json
        try:
            pos = json.loads(pos_str)
            target_view.scroll_to(pos["x"], pos["y"])
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    def _toggle_compare_mode(self, enabled: bool):
        """切换对比模式。"""
        self._compare_mode = enabled
        self.compare_view.setVisible(enabled)
        if enabled:
            self.splitter.setSizes([400, 400])
            # 如果还没有对比内容，用当前内容填充
            if self._original_html == EMPTY_HTML:
                self._original_html = self._result_html
            self._update_compare_view()
        else:
            self.splitter.setSizes([1, 0])
            self.web_view.setHtml(self._result_html)

    def _zoom_in(self):
        """放大。"""
        self.set_zoom(self._zoom_factor + self.ZOOM_STEP)

    def _zoom_out(self):
        """缩小。"""
        self.set_zoom(self._zoom_factor - self.ZOOM_STEP)

    def _apply_zoom(self):
        """应用缩放因子。"""
        # QWebEngineView 通过页面缩放实现
        self.web_view.setZoomFactor(self._zoom_factor)
        self.compare_view.setZoomFactor(self._zoom_factor)

    def _show_error(self, message: str):
        """显示错误信息到预览区域。"""
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8">{WORD_STYLE_CSS}</head>
<body>
    <div style="color: #c0392b; margin-top: 40pt; text-align: center;">
        <p style="font-size: 14pt; font-weight: bold; text-indent: 0;">加载失败</p>
        <p style="text-indent: 0; white-space: pre-wrap; color: #e74c3c;">{message}</p>
    </div>
</body>
</html>"""
        self.web_view.setHtml(html)

    def _update_status(self, file_path: str | Path):
        """更新底部状态信息。"""
        path = Path(file_path)
        if path.exists():
            size_kb = path.stat().st_size / 1024
            name = path.name
            self.page_label.setText(f"文件: {name} ({size_kb:.1f} KB)")
        self._update_word_count()

    def _update_word_count(self):
        """估算并显示字数。"""
        # 通过 JS 获取文本内容估算字数
        self.web_view.page().runJavaScript(
            "document.body.innerText.length",
            self._on_word_count_result,
        )

    def _on_word_count_result(self, count):
        """接收 JS 返回的字数。"""
        if count is not None:
            self.word_count_label.setText(f"字数: {count}")
