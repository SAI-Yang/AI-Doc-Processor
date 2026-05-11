"""文档生成面板

独立的文档生成界面，集成参考文档分析功能。
用户可以选择模板/输入提示词，添加参考文档，生成符合参考风格的文档。
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFrame, QTextEdit, QPlainTextEdit,
    QMessageBox, QSplitter, QGroupBox, QComboBox,
    QProgressBar, QFileDialog, QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QColor

from app.config import AppConfig
from app.llm_client import create_client, LLMError
from app.reference_analyzer import ReferenceAnalyzer
from app.template_manager import TemplateManager
from app.ui_reference import ReferenceManager

logger = logging.getLogger(__name__)


class GenerateWorker(QThread):
    """文档生成工作线程"""

    progress = pyqtSignal(str)       # 状态消息
    finished = pyqtSignal(str)       # 生成结果
    error = pyqtSignal(str)          # 错误信息

    def __init__(self, prompt: str, config: AppConfig, parent=None):
        super().__init__(parent)
        self.prompt = prompt
        self.config = config

    def run(self):
        """执行生成"""
        try:
            self.progress.emit("正在调用 API 生成文档...")
            client = create_client(self.config.llm)
            result = asyncio.run(
                client.process_content(
                    content="",
                    system_prompt="你是一名文档生成助手。严格按照用户的要求生成内容。",
                    user_prompt=self.prompt,
                )
            )
            self.finished.emit(result.strip())
        except LLMError as exc:
            self.error.emit(f"API 调用失败: {exc}")
        except ImportError as exc:
            self.error.emit(f"缺少依赖: {exc}")
        except Exception as exc:
            self.error.emit(f"生成失败: {exc}")


class GeneratePanel(QWidget):
    """文档生成面板

    布局:
    +--------------------------------------------------+
    | 📝 文档生成                                       |
    +--------------------------------------------------+
    | [模板选择下拉]  [设置: 温度/最大Token]            |
    +--------------------------------------------------+
    | 生成要求:                                         |
    | [多行输入框: 描述要生成什么文档]                  |
    +--------------------------------------------------+
    | 📎 参考文档区域 (ReferenceManager)                |
    +--------------------------------------------------+
    | [▶ 生成]  [生成中...]  ████████░░ 80%            |
    +--------------------------------------------------+
    | 生成结果:                                         |
    | [结果显示区]                                      |
    | [复制] [保存到文件]                               |
    +--------------------------------------------------+
    """

    # 生成完成信号
    generation_done = pyqtSignal(str, str)  # original_text, generated_text

    def __init__(self, config: Optional[AppConfig] = None, parent=None):
        super().__init__(parent)
        self._config = config or AppConfig.load()
        self._tm = TemplateManager()
        self._analyzer = ReferenceAnalyzer()
        self._worker: Optional[GenerateWorker] = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # ── 标题 ──────────────────────────────────────────
        title = QLabel("📝 文档生成")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1f2328;")
        layout.addWidget(title)

        # ── 模板选择 + 参数 ──────────────────────────────
        config_row = QHBoxLayout()
        config_row.setSpacing(8)

        config_row.addWidget(QLabel("模板:"))
        self.template_combo = QComboBox()
        self.template_combo.setMinimumWidth(160)
        self._load_templates()
        self.template_combo.currentIndexChanged.connect(self._on_template_changed)
        config_row.addWidget(self.template_combo)

        config_row.addStretch()

        config_row.addWidget(QLabel("温度:"))
        self.temp_combo = QComboBox()
        self.temp_combo.addItems(["0.1", "0.3", "0.5", "0.7", "1.0"])
        self.temp_combo.setCurrentText("0.3")
        self.temp_combo.setFixedWidth(60)
        config_row.addWidget(self.temp_combo)

        config_row.addWidget(QLabel("最大 Token:"))
        self.tokens_combo = QComboBox()
        self.tokens_combo.addItems(["1024", "2048", "4096", "8192", "16384"])
        self.tokens_combo.setCurrentText("4096")
        self.tokens_combo.setFixedWidth(80)
        config_row.addWidget(self.tokens_combo)

        layout.addLayout(config_row)

        # ── 生成要求输入 ─────────────────────────────────
        prompt_group = QGroupBox("生成要求")
        prompt_layout = QVBoxLayout(prompt_group)

        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setPlaceholderText(
            "描述要生成的文档内容、风格、格式等要求。\n"
            "例如：生成一份基于深度学习的图像分类实验报告，包括引言、方法、实验、结论。\n\n"
            "添加参考文档后，系统会自动参考其风格和结构。"
        )
        self.prompt_edit.setMinimumHeight(100)
        self.prompt_edit.setMaximumHeight(180)
        prompt_layout.addWidget(self.prompt_edit)

        layout.addWidget(prompt_group)

        # ── 参考文档区域（集成 ReferenceManager） ──────
        ref_group = QGroupBox("参考文档（可选）")
        ref_layout = QVBoxLayout(ref_group)
        ref_layout.setContentsMargins(0, 0, 0, 0)

        self.reference_mgr = ReferenceManager()
        self.reference_mgr.reference_added.connect(self._on_ref_added)
        self.reference_mgr.reference_selected.connect(self._on_ref_selected)
        ref_layout.addWidget(self.reference_mgr)

        layout.addWidget(ref_group)

        # ── 生成按钮 + 进度 ─────────────────────────────
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self.generate_btn = QPushButton("▶ 生成")
        self.generate_btn.setStyleSheet("""
            QPushButton {
                font-size: 14px; font-weight: bold; padding: 8px 24px;
                background-color: #238636; color: white;
                border: none; border-radius: 6px;
            }
            QPushButton:hover { background-color: #2ea043; }
            QPushButton:disabled { background-color: #8b949e; }
        """)
        self.generate_btn.clicked.connect(self._on_generate)
        action_row.addWidget(self.generate_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 不确定模式
        self.progress_bar.setFixedWidth(160)
        self.progress_bar.setFixedHeight(20)
        self.progress_bar.setVisible(False)
        action_row.addWidget(self.progress_bar)

        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #656d76; font-size: 12px;")
        action_row.addWidget(self.status_label, 1)

        layout.addLayout(action_row)

        # ── 结果区域 ────────────────────────────────────
        result_group = QGroupBox("生成结果")
        result_layout = QVBoxLayout(result_group)

        self.result_edit = QTextEdit()
        self.result_edit.setReadOnly(True)
        self.result_edit.setPlaceholderText("生成结果将在此显示...")
        self.result_edit.setFont(QFont("Microsoft YaHei UI", 11))
        result_layout.addWidget(self.result_edit)

        # 结果操作按钮
        result_actions = QHBoxLayout()
        result_actions.setSpacing(6)

        self.copy_btn = QPushButton("📋 复制")
        self.copy_btn.setEnabled(False)
        self.copy_btn.clicked.connect(self._copy_result)
        result_actions.addWidget(self.copy_btn)

        self.save_btn = QPushButton("💾 保存到文件")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save_result)
        result_actions.addWidget(self.save_btn)

        self.insert_ref_btn = QPushButton("📎 插入参考对比")
        self.insert_ref_btn.setToolTip("将参考分析建议插入到结果中，方便手工调整")
        self.insert_ref_btn.setEnabled(False)
        self.insert_ref_btn.clicked.connect(self._insert_ref_analysis)
        result_actions.addWidget(self.insert_ref_btn)

        result_actions.addStretch()
        result_layout.addLayout(result_actions)

        layout.addWidget(result_group, 1)

        # ── 提示词预览（折叠） ──────────────────────────
        self.preview_group = QGroupBox("发送给模型的完整提示词")
        self.preview_group.setVisible(False)
        preview_layout = QVBoxLayout(self.preview_group)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(200)
        self.preview_text.setFont(QFont("Consolas", 10))
        preview_layout.addWidget(self.preview_text)

        layout.addWidget(self.preview_group)

    # ── 内部方法 ──────────────────────────────────────────

    def _load_templates(self):
        """加载内置模板到下拉框"""
        self.template_combo.clear()
        templates = self._tm.list_templates()
        for t in templates:
            self.template_combo.addItem(t["name"], t["id"])

    def _on_template_changed(self, idx: int):
        """模板选择变更"""
        if idx < 0:
            return
        template_id = self.template_combo.itemData(idx)
        tpl = self._tm.get(template_id)
        if tpl:
            self.temp_combo.setCurrentText(f"{tpl.temperature:.1f}")
            self.tokens_combo.setCurrentText(str(tpl.max_tokens))

    def _on_ref_added(self, file_path: str):
        """参考文档添加后的回调"""
        count = self.reference_mgr.count()
        self.status_label.setText(f"已添加 {count} 个参考文档")

    def _on_ref_selected(self, analysis: dict):
        """参考文档选中后的回调"""
        # 在状态栏显示选中文档的分析摘要
        style = analysis.get("style", {})
        topics = analysis.get("key_topics", [])
        info = f"风格: {style.get('formality', '未知')} · {style.get('tone', '客观')}"
        if topics:
            info += f"  |  关键词: {'、'.join(topics[:5])}"
        self.status_label.setText(info)

    def _build_prompt(self) -> str:
        """构建完整的提示词（含参考文档上下文）

        Returns:
            完整的提示词字符串
        """
        user_prompt = self.prompt_edit.toPlainText().strip()
        template_id = self.template_combo.currentData()
        template_name = self.template_combo.currentText()

        parts: list[str] = []

        # 1. 模板提示词
        if template_id:
            tpl = self._tm.get(template_id)
            if tpl:
                parts.append(f"【处理模板: {template_name}】")
                parts.append(tpl.system_prompt)
                if tpl.user_prompt:
                    parts.append(tpl.user_prompt.replace("{content}", user_prompt or "{文档内容}"))

        # 2. 用户要求
        if user_prompt:
            if not template_id:
                parts.append("【用户要求】")
                parts.append(user_prompt)

        # 3. 参考文档上下文
        ref_texts = self.reference_mgr.get_reference_texts()
        ref_analyses = self.reference_mgr.get_reference_analysis()

        if ref_texts:
            ref_section_parts: list[str] = ["【参考文档】"]
            ref_section_parts.append("以下是参考文档的内容，请参考其风格、结构和格式进行生成：")
            ref_section_parts.append("")

            for i, (ref_text, ref_analysis) in enumerate(zip(ref_texts, ref_analyses)):
                ref_section_parts.append(f"--- 参考文档 {i + 1}: {ref_analysis.get('title', '未知')} ---")

                # 分析摘要
                style = ref_analysis.get("style", {})
                lang = "中文" if ref_analysis.get("language") == "zh" else "英文"
                ref_section_parts.append(f"语言: {lang} | 风格: {style.get('formality', '未知')} | 语气: {style.get('tone', '客观')}")

                hc = ref_analysis.get("heading_count", 0)
                if hc > 0:
                    ref_section_parts.append(f"章节结构: {hc} 个标题")
                if ref_analysis.get("table_count", 0) > 0:
                    ref_section_parts.append(f"包含 {ref_analysis['table_count']} 个表格")
                topics = ref_analysis.get("key_topics", [])
                if topics:
                    ref_section_parts.append(f"关键词: {'、'.join(topics[:6])}")

                ref_section_parts.append("")

                # 正文内容（截取前 2000 字）
                if ref_text:
                    ref_section_parts.append(ref_text[:2000])
                    if len(ref_text) > 2000:
                        ref_section_parts.append("...(内容较长，已截取前 2000 字)")
                ref_section_parts.append("")

            parts.append("\n".join(ref_section_parts))

        # 4. 生成指令
        parts.append("【要求】")
        if user_prompt:
            parts.append(f"请根据以上参考文档的风格和结构，{user_prompt}")
        else:
            parts.append("请根据以上参考文档的风格和结构，生成合适的文档内容。")
        parts.append("注意：严格遵循参考文档的格式规范。")

        return "\n\n".join(parts)

    def _on_generate(self):
        """点击生成按钮"""
        prompt = self._build_prompt()

        if not prompt.strip():
            QMessageBox.warning(self, "提示", "请输入生成要求或选择模板")
            return

        # 显示提示词预览
        if self.preview_group.isVisible():
            self.preview_text.setPlainText(prompt)

        # 更新 UI 状态
        self.generate_btn.setEnabled(False)
        self.generate_btn.setText("⏳ 生成中...")
        self.progress_bar.setVisible(True)
        self.status_label.setText("正在生成...")

        # 启动工作线程
        self._worker = GenerateWorker(prompt, self._config)
        self._worker.progress.connect(self._on_worker_progress)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()

    def _on_worker_progress(self, msg: str):
        self.status_label.setText(msg)

    def _on_worker_finished(self, result: str):
        """生成完成"""
        self.result_edit.setPlainText(result)
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("▶ 生成")
        self.progress_bar.setVisible(False)
        self.copy_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
        self.insert_ref_btn.setEnabled(self.reference_mgr.count() > 0)
        self.status_label.setText(f"生成完成 ({len(result)} 字)")
        self.generation_done.emit("", result)

    def _on_worker_error(self, msg: str):
        """生成出错"""
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("▶ 生成")
        self.progress_bar.setVisible(False)
        self.status_label.setText("生成失败")
        QMessageBox.critical(self, "生成失败", msg)

    def _copy_result(self):
        """复制结果到剪贴板"""
        text = self.result_edit.toPlainText()
        if text:
            from PyQt5.QtWidgets import QApplication
            QApplication.clipboard().setText(text)
            self.status_label.setText("已复制到剪贴板")

    def _save_result(self):
        """保存结果到文件"""
        text = self.result_edit.toPlainText()
        if not text:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "保存生成结果", "generated_doc.txt",
            "文本文件 (*.txt);;Markdown (*.md);;所有文件 (*.*)"
        )
        if path:
            try:
                Path(path).write_text(text, encoding="utf-8")
                QMessageBox.information(self, "保存成功", f"已保存到:\n{path}")
            except Exception as exc:
                QMessageBox.critical(self, "保存失败", str(exc))

    def _insert_ref_analysis(self):
        """将参考分析建议插入到结果末尾"""
        analyses = self.reference_mgr.get_reference_analysis()
        if not analyses:
            return

        current = self.result_edit.toPlainText()
        parts = [current, "", "=" * 40, "参考文档分析摘要:", ""]

        for i, analysis in enumerate(analyses):
            parts.append(f"[参考 {i + 1}] {analysis.get('title', '未知')}")
            style = analysis.get("style", {})
            topics = analysis.get("key_topics", [])
            hc = analysis.get("heading_count", 0)

            lines = []
            lines.append(f"  风格: {style.get('formality', '未知')}, {style.get('tone', '客观')}")
            if hc > 0:
                lines.append(f"  章节: {hc} 个标题")
            if topics:
                lines.append(f"  关键词: {'、'.join(topics[:8])}")
            lines.append(f"  字数: {analysis.get('word_count', 0)}")

            parts.extend(lines)
            parts.append("")

        self.result_edit.setPlainText("\n".join(parts))
        self.status_label.setText("已插入参考分析")

    # ── 对外接口 ──────────────────────────────────────────

    def set_prompt(self, text: str):
        """设置生成要求文本"""
        self.prompt_edit.setPlainText(text)

    def get_result(self) -> str:
        """获取生成结果"""
        return self.result_edit.toPlainText()

    def get_reference_analysis(self) -> list[dict]:
        """获取参考文档分析结果"""
        return self.reference_mgr.get_reference_analysis()

    def toggle_prompt_preview(self, visible: bool = False):
        """显示/隐藏提示词预览"""
        self.preview_group.setVisible(visible)
        if visible:
            self.preview_text.setPlainText(self._build_prompt())
