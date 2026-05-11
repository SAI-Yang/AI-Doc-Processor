"""文档生成面板 - 根据用户描述生成新文档"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QPushButton, QLabel, QFrame, QComboBox, QListWidget,
    QListWidgetItem, QFileDialog, QMessageBox,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from .generator import DocumentGenerator, DOC_FORMATS
from .config import AppConfig

logger = logging.getLogger(__name__)


# ── 后台工作线程（桥接 asyncio → Qt 信号）─────────────────────

class GenerateWorker(QThread):
    """文档生成工作线程

    在后台线程中运行 asyncio 事件循环，通过 Qt 信号将流式结果发回主线程。
    """

    chunk_received = pyqtSignal(str)   # 每收到一块增量文本
    finished = pyqtSignal(str)         # 生成完成，传完整文本
    error_occurred = pyqtSignal(str)   # 出错信息

    def __init__(self, generator: DocumentGenerator,
                 requirement: str, reference_texts: list[str],
                 format: str):
        super().__init__()
        self._generator = generator
        self._requirement = requirement
        self._reference_texts = reference_texts
        self._format = format

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            text = loop.run_until_complete(
                self._generator.generate(
                    requirement=self._requirement,
                    reference_texts=self._reference_texts,
                    format=self._format,
                    on_chunk=self._on_chunk,
                )
            )
            self.finished.emit(text)
        except Exception as e:
            logger.exception("生成线程异常")
            self.error_occurred.emit(str(e))
        finally:
            loop.close()

    def _on_chunk(self, chunk: str):
        """LLM 流式回调 — 跨线程发射信号"""
        self.chunk_received.emit(chunk)


# ── 文档生成面板 ─────────────────────────────────────────────

class GeneratePanel(QWidget):
    """文档生成面板 — 根据用户描述生成新文档"""

    # ── 信号 ───────────────────────────────────────────────
    generate_started = pyqtSignal()              # 开始生成
    generate_finished = pyqtSignal(str)          # 生成完成，传递完整文本
    chunk_received = pyqtSignal(str)             # 流式文本块
    preview_requested = pyqtSignal(str)          # 请求预览
    save_requested = pyqtSignal(str)             # 保存完成，传递路径

    def __init__(self, parent=None):
        super().__init__(parent)
        self._config: Optional[AppConfig] = None
        self._generator: Optional[DocumentGenerator] = None
        self._worker: Optional[GenerateWorker] = None
        self._generated_text: str = ""
        self._reference_paths: list[Path] = []

        self._build_ui()

    # ── 布局 ───────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # ── 标题栏 ──────────────────────────────────────
        title_bar = QFrame()
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel('📝 文档生成')
        title_label.setStyleSheet(
            'font-size: 16px; font-weight: bold; color: #24292f;'
        )
        title_layout.addWidget(title_label)

        title_layout.addStretch()

        mode_hint = QLabel('生成模式')
        mode_hint.setStyleSheet('color: #58a6ff; font-size: 12px;')
        title_layout.addWidget(mode_hint)

        layout.addWidget(title_bar)

        # ── 需求描述 ──────────────────────────────────────
        req_label = QLabel('你的需求描述：')
        req_label.setStyleSheet('font-weight: 500; color: #24292f;')
        layout.addWidget(req_label)

        self.req_edit = QPlainTextEdit()
        self.req_edit.setPlaceholderText(
            '请描述你想要生成的文档内容，例如：\n'
            '请帮我生成一份关于XX项目技术方案的文档，包含项目背景、'
            '技术架构、实施方案、风险分析等章节。'
        )
        self.req_edit.setMinimumHeight(140)
        self.req_edit.setStyleSheet("""
            QPlainTextEdit {
                border: 1px solid #d0d7de;
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
                background: #ffffff;
                color: #24292f;
            }
            QPlainTextEdit:focus {
                border-color: #58a6ff;
            }
        """)
        layout.addWidget(self.req_edit, 2)

        # ── 参考文档 ──────────────────────────────────────
        ref_label = QLabel('参考文档（可选，拖拽或点击添加）：')
        ref_label.setStyleSheet('font-weight: 500; color: #24292f;')
        layout.addWidget(ref_label)

        ref_btn_bar = QHBoxLayout()
        ref_btn_bar.setSpacing(6)

        self.btn_add_ref = QPushButton('📎 添加参考文档')
        self.btn_add_ref.setCursor(Qt.PointingHandCursor)
        self.btn_add_ref.clicked.connect(self._add_reference_files)
        ref_btn_bar.addWidget(self.btn_add_ref)

        self.btn_clear_ref = QPushButton('清空')
        self.btn_clear_ref.setVisible(False)
        self.btn_clear_ref.clicked.connect(self._clear_references)
        ref_btn_bar.addWidget(self.btn_clear_ref)

        ref_btn_bar.addStretch()
        layout.addLayout(ref_btn_bar)

        self.ref_list = QListWidget()
        self.ref_list.setMaximumHeight(72)
        self.ref_list.setAlternatingRowColors(True)
        self.ref_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #d0d7de;
                border-radius: 6px;
                background: #f6f8fa;
                padding: 4px;
                color: #24292f;
            }
        """)
        layout.addWidget(self.ref_list)

        # ── 格式选择 ──────────────────────────────────────
        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(8)

        fmt_label = QLabel('文档格式：')
        fmt_label.setStyleSheet('font-weight: 500; color: #24292f;')
        fmt_row.addWidget(fmt_label)

        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(list(DOC_FORMATS.keys()))
        self.fmt_combo.setCurrentText('技术报告')
        self.fmt_combo.setMinimumWidth(140)
        fmt_row.addWidget(self.fmt_combo)

        fmt_row.addSpacing(16)

        out_hint = QLabel('📄 DOCX')
        out_hint.setStyleSheet('color: #57606a; font-size: 13px;')
        fmt_row.addWidget(out_hint)

        fmt_row.addStretch()
        layout.addLayout(fmt_row)

        # ── 操作按钮 ──────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_generate = QPushButton('▶ 生成文档')
        self.btn_generate.setObjectName('generateBtn')
        self.btn_generate.setMinimumHeight(36)
        self.btn_generate.setCursor(Qt.PointingHandCursor)
        self.btn_generate.setStyleSheet("""
            QPushButton#generateBtn {
                background: #2da44e;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton#generateBtn:hover {
                background: #218838;
            }
            QPushButton#generateBtn:disabled {
                background: #94d3a2;
            }
            QPushButton#generateBtn:pressed {
                background: #1e7e34;
            }
        """)
        self.btn_generate.clicked.connect(self._start_generate)
        btn_row.addWidget(self.btn_generate)

        self.btn_preview = QPushButton('📋 预览')
        self.btn_preview.setMinimumHeight(36)
        self.btn_preview.setEnabled(False)
        self.btn_preview.clicked.connect(self._request_preview)
        btn_row.addWidget(self.btn_preview)

        self.btn_save = QPushButton('💾 保存')
        self.btn_save.setMinimumHeight(36)
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._save_document)
        btn_row.addWidget(self.btn_save)

        self.btn_cancel = QPushButton('取消')
        self.btn_cancel.setMinimumHeight(36)
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self._cancel_generate)
        btn_row.addWidget(self.btn_cancel)

        btn_row.addStretch()
        layout.addLayout(btn_row)

    # ── 公开方法 ───────────────────────────────────────────

    def set_config(self, config: AppConfig):
        """更新配置（设置变更后调用）"""
        self._config = config
        self._generator = DocumentGenerator(config)

    def get_config(self) -> dict:
        """返回当前配置"""
        return {
            'mode': 'generate',
            'requirement': self.req_edit.toPlainText(),
            'reference_paths': [str(p) for p in self._reference_paths],
            'format': self.fmt_combo.currentText(),
        }

    def cancel_generation(self):
        """取消正在进行的生成任务（外部调用，如模式切换）"""
        self._cancel_generate()

    # ── 槽函数 ─────────────────────────────────────────────

    def _add_reference_files(self):
        """选择参考文档"""
        paths, _ = QFileDialog.getOpenFileNames(
            self, '选择参考文档', '',
            '所有支持的文件 (*.docx *.pdf *.txt *.md);;'
            'Word 文档 (*.docx);;PDF 文档 (*.pdf);;'
            '文本文件 (*.txt);;Markdown (*.md);;所有文件 (*.*)'
        )
        if not paths:
            return

        for p in paths:
            fp = Path(p)
            if fp not in self._reference_paths:
                self._reference_paths.append(fp)
                item = QListWidgetItem(f'{fp.name}  ✓')
                item.setToolTip(str(fp))
                self.ref_list.addItem(item)

        self.btn_clear_ref.setVisible(len(self._reference_paths) > 0)

    def _clear_references(self):
        """清空参考文档列表"""
        self._reference_paths.clear()
        self.ref_list.clear()
        self.btn_clear_ref.setVisible(False)

    def _start_generate(self):
        """开始生成文档"""
        requirement = self.req_edit.toPlainText().strip()
        if not requirement:
            QMessageBox.information(self, '提示', '请先输入需求描述')
            return

        if not self._config or not self._config.llm.api_key:
            QMessageBox.warning(self, 'API 未配置', '请先在设置中配置 API Key')
            return

        # 读取参考文档
        reference_texts = self._read_reference_texts()
        fmt = self.fmt_combo.currentText()

        # UI 进入生成状态
        self._generated_text = ""
        self._set_ui_busy(True)
        self.generate_started.emit()

        # 创建工作线程
        self._worker = GenerateWorker(
            self._generator, requirement, reference_texts, fmt
        )
        self._worker.chunk_received.connect(self._on_chunk)
        self._worker.finished.connect(self._on_finished)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.start()

    def _cancel_generate(self):
        """取消生成"""
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait()
            self._worker = None
        self._set_ui_busy(False)

    def _request_preview(self):
        """请求预览生成的文档"""
        if self._generated_text:
            self.preview_requested.emit(self._generated_text)

    def _save_document(self):
        """保存生成的文档为 .docx"""
        if not self._generated_text:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, '保存文档', 'generated_document.docx',
            'Word 文档 (*.docx);;文本文件 (*.txt);;所有文件 (*.*)'
        )
        if not path:
            return

        try:
            output_path = Path(path)
            if output_path.suffix.lower() == '.txt':
                output_path.write_text(self._generated_text, encoding='utf-8')
            else:
                # 从需求首行提取文档标题
                lines = self.req_edit.toPlainText().strip().split('\n')
                title = lines[0][:50] if lines else '未命名文档'
                self._generator.save_as_docx(
                    self._generated_text, output_path, title
                )

            QMessageBox.information(self, '保存成功', f'已保存到:\n{output_path}')
            self.save_requested.emit(str(output_path))
        except Exception as e:
            logger.exception("保存失败")
            QMessageBox.critical(self, '保存失败', str(e))

    # ── 内部方法 ───────────────────────────────────────────

    def _read_reference_texts(self) -> list[str]:
        """读取参考文档的文本内容"""
        texts = []
        for path in self._reference_paths:
            try:
                from app.document import read_document
                doc = read_document(path)
                texts.append(doc.content)
            except Exception as e:
                QMessageBox.warning(
                    self, '读取失败',
                    f'无法读取参考文档: {path.name}\n{str(e)}'
                )
        return texts

    def _set_ui_busy(self, busy: bool):
        """设置生成中的 UI 状态"""
        self.btn_generate.setEnabled(not busy)
        self.btn_generate.setText(
            '⏳ 生成中...' if busy else '▶ 生成文档'
        )
        self.btn_cancel.setVisible(busy)
        self.btn_preview.setEnabled(not busy and bool(self._generated_text))
        self.btn_save.setEnabled(not busy and bool(self._generated_text))
        self.req_edit.setReadOnly(busy)
        self.fmt_combo.setEnabled(not busy)
        self.btn_add_ref.setEnabled(not busy)

    def _on_chunk(self, chunk: str):
        """收到流式文本块"""
        self._generated_text += chunk
        self.chunk_received.emit(chunk)

    def _on_finished(self, full_text: str):
        """生成完成"""
        self._generated_text = full_text
        self._worker = None
        self._set_ui_busy(False)
        self.generate_finished.emit(full_text)

    def _on_error(self, msg: str):
        """生成出错"""
        self._worker = None
        self._set_ui_busy(False)
        QMessageBox.critical(self, '生成失败', f'文档生成失败:\n{msg}')
        # 即使出错也可能有部分内容
        self.generate_finished.emit(self._generated_text)
