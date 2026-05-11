"""图表生成与插入对话框

提供自然语言描述输入、图表类型选择、CSV 数据输入、
实时预览、以及插入文档的功能。
"""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QMessageBox, QComboBox, QPlainTextEdit,
    QSizePolicy, QSplitter, QFileDialog, QTextEdit, QWidget,
    QTabWidget, QCheckBox,
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap, QFont, QImage

logger = logging.getLogger(__name__)


class FigureInsertDialog(QDialog):
    """图表生成与插入对话框。

    布局：
    +--------------------------------------------------+
    |  生成科学图表                           ×        |
    +--------------------------------------------------+
    |  图表描述：                                       |
    |  [输入框：如"绘制信号处理前后的频谱对比图"]      |
    |                                                  |
    |  图表类型：[折线图 ▼]  风格：[Nature ▼]         |
    |                                                  |
    |  数据输入（可选）：                               |
    |  [多行文本框：支持 CSV 格式或直接描述]           |
    |                                                  |
    |  [预览图表]  [插入到文档]                        |
    +--------------------------------------------------+
    """

    def __init__(self, docx_path: str = "", parent=None):
        """
        Args:
            docx_path: 目标文档路径（为空则只生成图片不插入）
            parent: 父窗口
        """
        super().__init__(parent)
        try:
            from app.figure_generator import FigureGenerator
            self._FigureGenerator = FigureGenerator
        except ImportError:
            QMessageBox.critical(
                self, '缺少依赖',
                '需要安装 matplotlib 库才能生成图表。\n请运行: pip install matplotlib',
            )
            self.reject()
            return

        self.CHART_TYPE_KEYS = list(FigureGenerator.CHART_TYPES.keys())
        self.CHART_TYPE_NAMES = list(FigureGenerator.CHART_TYPES.values())
        self._docx_path = docx_path
        self._generator = FigureGenerator()
        self._generated_path: str = ""
        self._generated_bytes: bytes = b""

        self._build_ui()
        self._apply_style()

    # ── 布局 ──────────────────────────────────────────────

    def _build_ui(self):
        self.setWindowTitle('生成科学图表')
        self.setMinimumSize(700, 600)
        self.setMaximumSize(1000, 800)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        # ── 标题 ──────────────────────────────────────
        title_label = QLabel('生成科学图表')
        title_label.setStyleSheet(
            'font-size: 16px; font-weight: bold; color: #1f2328;'
            ' margin-bottom: 4px;'
        )
        layout.addWidget(title_label)

        # ── 文档信息（如果有） ─────────────────────────
        if self._docx_path:
            doc_label = QLabel(f'目标文档: {Path(self._docx_path).name}')
            doc_label.setStyleSheet('font-size: 11px; color: #7f8c8d;')
            layout.addWidget(doc_label)

        # ── 图表描述 ──────────────────────────────────
        desc_label = QLabel('图表描述:')
        desc_label.setStyleSheet('font-size: 12px; font-weight: 500; color: #333;')
        layout.addWidget(desc_label)

        self._desc_edit = QLineEdit()
        self._desc_edit.setPlaceholderText(
            '如：绘制频率为x轴、幅值为y轴的频谱图，或 绘制A/B/C三种模型的性能对比柱状图'
        )
        self._desc_edit.setMinimumHeight(36)
        self._desc_edit.textChanged.connect(self._on_input_changed)
        layout.addWidget(self._desc_edit)

        # 示例提示
        hint = QLabel(
            '示例: "频谱图" "滤波前后对比" "模型性能对比" "实验数据带误差棒" "流程图"'
        )
        hint.setStyleSheet('font-size: 11px; color: #959da5;')
        layout.addWidget(hint)

        # ── 图表类型 + 参数行 ─────────────────────────
        config_row = QHBoxLayout()
        config_row.setSpacing(12)

        config_row.addWidget(QLabel('图表类型:'))
        self._type_combo = QComboBox()
        self._type_combo.addItems(self.CHART_TYPE_NAMES)
        self._type_combo.setCurrentText('折线图')
        self._type_combo.setMinimumWidth(110)
        config_row.addWidget(self._type_combo)

        config_row.addWidget(QLabel('DPI:'))
        self._dpi_combo = QComboBox()
        self._dpi_combo.addItems(['150', '300', '600'])
        self._dpi_combo.setCurrentText('300')
        self._dpi_combo.setFixedWidth(70)
        config_row.addWidget(self._dpi_combo)

        self._auto_type_check = QCheckBox('自动识别')
        self._auto_type_check.setChecked(True)
        self._auto_type_check.toggled.connect(self._on_auto_type_toggled)
        config_row.addWidget(self._auto_type_check)

        config_row.addStretch()
        layout.addLayout(config_row)

        # ── 数据输入（可选） ──────────────────────────
        data_tabs = QTabWidget()
        data_tabs.setDocumentMode(True)

        # Tab 1: CSV 数据输入
        csv_widget = QWidget()
        csv_layout = QVBoxLayout(csv_widget)
        csv_layout.setContentsMargins(0, 6, 0, 0)
        csv_layout.setSpacing(4)

        csv_hint = QLabel(
            '可选的 CSV 数据（首行为列名，留空则生成示例数据）:'
        )
        csv_hint.setStyleSheet('font-size: 11px; color: #666;')
        csv_layout.addWidget(csv_hint)

        self._data_edit = QPlainTextEdit()
        self._data_edit.setPlaceholderText(
            'x,y\n'
            '1,2.3\n'
            '2,4.1\n'
            '3,5.8\n'
            '4,7.2\n\n'
            '支持逗号或制表符分隔'
        )
        self._data_edit.setMaximumHeight(120)
        self._data_edit.setFont(QFont('Consolas', 10))
        csv_layout.addWidget(self._data_edit)

        data_tabs.addTab(csv_widget, 'CSV 数据（可选）')

        # Tab 2: 预设模板
        template_widget = QWidget()
        template_layout = QVBoxLayout(template_widget)
        template_layout.setContentsMargins(0, 6, 0, 0)
        template_layout.setSpacing(4)

        tmpl_hint = QLabel('选择一个预设模板快速生成:')
        tmpl_hint.setStyleSheet('font-size: 11px; color: #666;')
        template_layout.addWidget(tmpl_hint)

        self._template_combo = QComboBox()
        self._template_combo.addItems([
            '无模板（手动描述）',
            '频谱图 — 频率 vs 幅值',
            '滤波对比图 — 原始 vs 滤波后',
            '实验数据图 — 带误差棒',
            '模型性能对比 — 多模型柱状图',
            '流程示意图 — 步骤框图',
        ])
        self._template_combo.currentIndexChanged.connect(self._on_template_selected)
        template_layout.addWidget(self._template_combo)

        # 模板参数区域
        self._template_params_layout = QVBoxLayout()
        template_layout.addLayout(self._template_params_layout)
        template_layout.addStretch()

        data_tabs.addTab(template_widget, '预设模板')

        # Tab 3: 数据描述（自然语言）
        desc_data_widget = QWidget()
        desc_data_layout = QVBoxLayout(desc_data_widget)
        desc_data_layout.setContentsMargins(0, 6, 0, 0)
        desc_data_layout.setSpacing(4)

        desc_data_hint = QLabel(
            '用自然语言描述数据趋势（留空则从图表描述自动推断）:'
        )
        desc_data_hint.setStyleSheet('font-size: 11px; color: #666;')
        desc_data_layout.addWidget(desc_data_hint)

        self._data_desc_edit = QTextEdit()
        self._data_desc_edit.setMaximumHeight(100)
        self._data_desc_edit.setPlaceholderText(
            '例如：x 从 1 到 10，y 呈指数增长，在 x=5 处有一个峰值...'
        )
        desc_data_layout.addWidget(self._data_desc_edit)

        data_tabs.addTab(desc_data_widget, '数据描述')

        layout.addWidget(data_tabs)

        # ── 预览区域 ──────────────────────────────────
        preview_frame = QFrame()
        preview_frame.setObjectName('figurePreviewFrame')
        preview_frame.setStyleSheet(
            '#figurePreviewFrame {'
            '  background: #f8f9fa;'
            '  border: 1px solid #d0d7de;'
            '  border-radius: 8px;'
            '}'
        )
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        preview_layout.setSpacing(4)

        preview_header = QHBoxLayout()
        preview_label = QLabel('预览')
        preview_label.setStyleSheet(
            'font-size: 12px; font-weight: 600; color: #555;'
        )
        preview_header.addWidget(preview_label)
        preview_header.addStretch()

        self._preview_size_label = QLabel('')
        self._preview_size_label.setStyleSheet(
            'font-size: 11px; color: #959da5;'
        )
        preview_header.addWidget(self._preview_size_label)
        preview_layout.addLayout(preview_header)

        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignCenter)
        self._preview_label.setMinimumSize(400, 220)
        self._preview_label.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        self._preview_label.setStyleSheet(
            'color: #959da5; font-size: 13px;'
        )
        self._preview_label.setText('输入描述后点击"生成预览"')
        preview_layout.addWidget(self._preview_label, 1)

        layout.addWidget(preview_frame, 1)

        # ── 操作按钮 ──────────────────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self._preview_btn = QPushButton('🔍 生成预览')
        self._preview_btn.setObjectName('previewBtn')
        self._preview_btn.clicked.connect(self._on_preview)
        btn_layout.addWidget(self._preview_btn)

        btn_layout.addStretch()

        self._save_btn = QPushButton('💾 保存图片')
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save_image)
        btn_layout.addWidget(self._save_btn)

        self._insert_btn = QPushButton('📄 插入到文档')
        self._insert_btn.setObjectName('insertBtn')
        self._insert_btn.setEnabled(False)
        self._insert_btn.clicked.connect(self._on_insert)
        btn_layout.addWidget(self._insert_btn)

        self._close_btn = QPushButton('取消')
        self._close_btn.setFixedWidth(80)
        self._close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._close_btn)

        layout.addLayout(btn_layout)

    # ── 样式 ──────────────────────────────────────────────

    def _apply_style(self):
        self.setStyleSheet("""
            QDialog {
                background: #ffffff;
            }
            QLineEdit {
                background: #ffffff;
                border: 1px solid #d0d7de;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
                selection-background-color: #cce5ff;
            }
            QLineEdit:focus {
                border-color: #4a90d9;
            }
            QPlainTextEdit, QTextEdit {
                background: #ffffff;
                border: 1px solid #d0d7de;
                border-radius: 6px;
                padding: 6px 8px;
                font-size: 12px;
                selection-background-color: #cce5ff;
            }
            QPlainTextEdit:focus, QTextEdit:focus {
                border-color: #4a90d9;
            }
            QComboBox {
                background: #ffffff;
                border: 1px solid #d0d7de;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 12px;
                min-height: 24px;
            }
            QComboBox:hover {
                border-color: #4a90d9;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QPushButton {
                background: #ffffff;
                border: 1px solid #d0d7de;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 13px;
                color: #24292f;
                min-height: 28px;
            }
            QPushButton:hover {
                background: #f0f4ff;
                border-color: #4a90d9;
            }
            QPushButton:pressed {
                background: #dde6ff;
            }
            QPushButton#previewBtn {
                background: #6f42c1;
                color: #ffffff;
                border: none;
                font-weight: 600;
            }
            QPushButton#previewBtn:hover {
                background: #5a32a3;
            }
            QPushButton#insertBtn {
                background: #238636;
                color: #ffffff;
                border: none;
                font-weight: 600;
            }
            QPushButton#insertBtn:hover {
                background: #2ea043;
            }
            QPushButton#insertBtn:disabled {
                background: #8b949e;
            }
            QCheckBox {
                font-size: 12px;
                color: #555;
            }
            QTabWidget::pane {
                border: 1px solid #d0d7de;
                border-radius: 4px;
                background: #ffffff;
            }
            QTabBar::tab {
                font-size: 11px;
                padding: 4px 12px;
                border: 1px solid transparent;
                border-bottom: none;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                border-color: #d0d7de;
                border-bottom: 2px solid #4a90d9;
            }
        """)

        # 预置 QLabel 的 hover 预览效果

    # ── 信号处理 ──────────────────────────────────────────

    def _on_input_changed(self):
        """输入文本变化时自动更新（不做实时预览，仅 UI 反馈）。"""
        pass

    def _on_auto_type_toggled(self, checked: bool):
        """自动识别图表类型开关。"""
        self._type_combo.setEnabled(not checked)

    def _on_template_selected(self, idx: int):
        """预设模板选择后自动填充描述。"""
        templates = {
            1: ('频谱图', '绘制x轴为频率(Hz)、y轴为幅值的频谱图，显示信号在频域中的分布'),
            2: ('滤波前后对比', '绘制原始信号与滤波后信号的时域对比图，显示滤波效果'),
            3: ('实验数据', '绘制带误差棒的实验数据折线图，x轴为参数，y轴为测量值'),
            4: ('模型性能对比', '绘制多种模型性能对比柱状图，比较各模型的准确率'),
            5: ('流程示意图', '绘制算法/实验流程图，显示各步骤之间的关系'),
        }

        if idx == 0:
            return

        chart_type, desc = templates.get(idx, ('', ''))
        if chart_type:
            self._desc_edit.setText(desc)
            # 自动设置图表类型
            type_map = {
                '频谱图': 'line',
                '滤波前后对比': 'multiline',
                '实验数据': 'line',
                '模型性能对比': 'bar',
                '流程示意图': 'bar',  # 流程用 render_flow_diagram 是特殊处理
            }
            ctype = type_map.get(chart_type, 'line')
            keys = list(self._FigureGenerator.CHART_TYPES.keys())
            if ctype in keys:
                self._type_combo.setCurrentIndex(keys.index(ctype))
                self._auto_type_check.setChecked(False)

    def _on_preview(self):
        """生成预览图表。"""
        description = self._desc_edit.text().strip()
        if not description:
            QMessageBox.warning(self, '提示', '请输入图表描述')
            return

        # 确定图表类型
        if self._auto_type_check.isChecked():
            chart_type = 'auto'
        else:
            idx = self._type_combo.currentIndex()
            chart_type = self.CHART_TYPE_KEYS[idx]

        # 尝试从数据输入中读取 CSV 数据
        csv_text = self._data_edit.toPlainText().strip()
        data = {}
        if csv_text:
            try:
                data = self._FigureGenerator.parse_csv_data(csv_text)
            except Exception as e:
                logger.warning("CSV 解析失败，使用示例数据: %s", e)

        # 预设模板特殊处理
        template_idx = self._template_combo.currentIndex()
        template_handlers = {
            1: ('spectrum', {}),
            2: ('filter_comparison', {}),
            3: ('experiment_data', {}),
            4: ('model_comparison', {}),
            5: ('flow_diagram', {}),
        }

        if template_idx in template_handlers:
            handler_name, _ = template_handlers[template_idx]
            # 用模板渲染
            import tempfile
            tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            tmp.close()
            tmp_path = tmp.name

            try:
                if handler_name == 'spectrum':
                    self._generator.render_spectrum(tmp_path, title=description)
                elif handler_name == 'filter_comparison':
                    self._generator.render_filter_comparison(tmp_path, title=description)
                elif handler_name == 'experiment_data':
                    self._generator.render_experiment_data(tmp_path, title=description)
                elif handler_name == 'model_comparison':
                    self._generator.render_model_comparison(tmp_path, title=description)
                elif handler_name == 'flow_diagram':
                    # 从描述中提取步骤名
                    steps = [s.strip() for s in description.replace('，', ',').split(',') if s.strip()]
                    self._generator.render_flow_diagram(tmp_path, steps=steps or None, title=description)

                self._generated_path = tmp_path
                # 读取 bytes 用于可能的插入操作
                with open(tmp_path, 'rb') as f:
                    self._generated_bytes = f.read()

                self._show_preview(tmp_path)
                self._insert_btn.setEnabled(bool(self._docx_path))
                self._save_btn.setEnabled(True)
                self._preview_size_label.setText(
                    f'{len(self._generated_bytes) // 1024} KB | {self._dpi_combo.currentText()} DPI'
                )
                return
            except Exception as e:
                Path(tmp_path).unlink(missing_ok=True)
                logger.error("模板渲染失败: %s", e)
                # fallthrough 到通用生成

        # 通用生成
        try:
            # 暂存到临时文件
            import tempfile
            tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            tmp.close()
            tmp_path = tmp.name

            dpi = int(self._dpi_combo.currentText())
            self._generator._dpi = dpi

            out_path = self._generator.generate(
                description=description,
                output_path=tmp_path,
                chart_type=chart_type,
                data=data,
            )

            self._generated_path = out_path
            with open(out_path, 'rb') as f:
                self._generated_bytes = f.read()

            self._show_preview(out_path)
            self._insert_btn.setEnabled(bool(self._docx_path))
            self._save_btn.setEnabled(True)
            self._preview_size_label.setText(
                f'{len(self._generated_bytes) // 1024} KB | {dpi} DPI'
            )
        except Exception as e:
            logger.exception("图表生成失败")
            QMessageBox.critical(self, '生成失败', f'{type(e).__name__}: {e}')

    def _on_insert(self):
        """将图表插入到文档中。"""
        if not self._docx_path:
            QMessageBox.warning(self, '提示', '未指定目标文档')
            return

        if not self._generated_bytes:
            QMessageBox.warning(self, '提示', '请先生成图表')
            return

        try:
            out_path = self._generator.insert_into_docx(
                self._docx_path, self._generated_bytes,
            )
            QMessageBox.information(
                self, '插入成功',
                f'图表已插入到文档。\n\n保存位置: {out_path}',
            )
            self.accept()
        except ImportError as e:
            QMessageBox.critical(
                self, '缺少依赖',
                f'需要安装 python-docx: pip install python-docx\n\n{type(e).__name__}: {e}',
            )
        except FileNotFoundError as e:
            QMessageBox.critical(self, '文件不存在', str(e))
        except Exception as e:
            logger.exception("插入图表到文档失败")
            QMessageBox.critical(self, '插入失败', f'{type(e).__name__}: {e}')

    def _on_save_image(self):
        """保存生成的图表图片到文件。"""
        if not self._generated_path:
            QMessageBox.warning(self, '提示', '请先生成图表')
            return

        path, _ = QFileDialog.getSaveFileName(
            self, '保存图表', f'chart_{self._desc_edit.text()[:20].strip() or "figure"}.png',
            'PNG 图片 (*.png);;JPEG 图片 (*.jpg);;TIFF 图片 (*.tiff);;PDF (*.pdf);;所有文件 (*.*)',
        )
        if not path:
            return

        try:
            # 用原始生成路径复制到目标路径
            from shutil import copy2
            copy2(self._generated_path, path)
            QMessageBox.information(self, '保存成功', f'图表已保存到:\n{path}')
        except Exception as e:
            QMessageBox.critical(self, '保存失败', str(e))

    # ── 预览显示 ──────────────────────────────────────────

    def _show_preview(self, image_path: str):
        """在预览区域显示图表图片。"""
        pix = QPixmap(image_path)
        if pix.isNull():
            self._preview_label.setText('预览加载失败')
            return

        # 缩放适应预览区域
        max_w = self._preview_label.width() - 16
        max_h = self._preview_label.height() - 16
        if max_w <= 0 or max_h <= 0:
            max_w, max_h = 500, 280

        scaled = pix.scaled(
            max_w, max_h, Qt.KeepAspectRatio, Qt.SmoothTransformation,
        )
        self._preview_label.setPixmap(scaled)

    def resizeEvent(self, event):
        """窗口大小变化时重新缩放预览。"""
        super().resizeEvent(event)
        if self._generated_path and self._preview_label.pixmap():
            self._show_preview(self._generated_path)
