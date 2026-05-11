"""图片插入对话框

提供图片选择、位置指定、智能推荐预览和确认插入功能。
"""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QLineEdit, QFrame, QMessageBox, QDialogButtonBox,
    QSizePolicy, QSpacerItem,
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QPixmap, QIcon

from app.image_placer import ImagePlacer, SUPPORTED_IMAGE_FORMATS

logger = logging.getLogger(__name__)


class ImageInsertDialog(QDialog):
    """图片插入对话框。

    打开现有 .docx 文档，选择图片，指定或自动识别插入位置，
    确认后直接修改文档并保存副本。
    """

    def __init__(self, docx_path: str, parent=None):
        super().__init__(parent)
        self._docx_path = docx_path
        self._image_path: str = ""
        self._placer = ImagePlacer()
        self._recommendation: dict = {}
        self._paragraphs: list[dict] = []

        # 分析文档（一打开就分析，后续推荐秒出）
        try:
            self._paragraphs = self._placer.analyze_document(docx_path)
        except Exception as e:
            logger.warning("文档分析失败（稍后重试）: %s", e)

        self._build_ui()
        self._apply_style()
        self._update_recommendation()

    # ── 布局 ──────────────────────────────────────────────

    def _build_ui(self):
        self.setWindowTitle('插入图片')
        self.setMinimumSize(520, 420)
        self.setMaximumSize(700, 600)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 18, 20, 18)

        # ── 文档信息 ──────────────────────────────────
        doc_label = QLabel(f'当前文档: {Path(self._docx_path).name}')
        doc_label.setStyleSheet('font-size: 12px; color: #7f8c8d;')
        doc_label.setWordWrap(True)
        layout.addWidget(doc_label)

        # ── 图片文件选择 ──────────────────────────────
        file_layout = QHBoxLayout()
        file_label = QLabel('图片文件:')
        file_label.setFixedWidth(70)
        file_layout.addWidget(file_label)

        self._file_path_edit = QLineEdit()
        self._file_path_edit.setPlaceholderText('选择要插入的图片...')
        self._file_path_edit.setReadOnly(True)
        file_layout.addWidget(self._file_path_edit, 1)

        self._browse_btn = QPushButton('选择...')
        self._browse_btn.setFixedWidth(80)
        self._browse_btn.clicked.connect(self._on_browse_image)
        file_layout.addWidget(self._browse_btn)

        layout.addLayout(file_layout)

        # 格式提示
        fmt_hint = QLabel('支持: PNG / JPG / JPEG / BMP / GIF / TIFF')
        fmt_hint.setStyleSheet('font-size: 11px; color: #959da5;')
        fmt_hint.setContentsMargins(70, 0, 0, 0)
        layout.addWidget(fmt_hint)

        # ── 位置说明 ──────────────────────────────────
        pos_layout = QHBoxLayout()
        pos_label = QLabel('位置说明（可选）:')
        pos_label.setFixedWidth(100)
        pos_layout.addWidget(pos_label)

        self._pos_input = QLineEdit()
        self._pos_input.setPlaceholderText('如：实验结果后面、第3段后面、开头、末尾')
        self._pos_input.textChanged.connect(self._update_recommendation)
        pos_layout.addWidget(self._pos_input, 1)

        layout.addLayout(pos_layout)

        # 提示
        hint = QLabel('提示：留空则自动识别最佳位置')
        hint.setStyleSheet('font-size: 11px; color: #959da5;')
        hint.setContentsMargins(100, 0, 0, 0)
        layout.addWidget(hint)

        # ── 智能推荐卡片 ──────────────────────────────
        card = QFrame()
        card.setObjectName('recommendCard')
        card.setStyleSheet(
            '#recommendCard {'
            '  background: #f0f6ff;'
            '  border: 1px solid #c8dfff;'
            '  border-radius: 8px;'
            '  padding: 12px;'
            '}'
        )
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(4)

        card_title = QLabel('智能推荐')
        card_title.setStyleSheet(
            'font-size: 13px; font-weight: 600; color: #4a90d9;'
        )
        card_layout.addWidget(card_title)

        self._recommend_label = QLabel(
            '选择图片后自动生成推荐位置'
        )
        self._recommend_label.setWordWrap(True)
        self._recommend_label.setStyleSheet(
            'font-size: 12px; color: #2c3e50; line-height: 1.5;'
        )
        card_layout.addWidget(self._recommend_label)

        # 段落图片预览（如有）
        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignCenter)
        self._preview_label.setMinimumHeight(60)
        self._preview_label.setVisible(False)
        card_layout.addWidget(self._preview_label)

        layout.addWidget(card, 1)

        # ── 按钮 ──────────────────────────────────────
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._confirm_btn = QPushButton('确认插入')
        self._confirm_btn.setObjectName('confirmBtn')
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.setFixedHeight(34)
        self._confirm_btn.setMinimumWidth(100)
        self._confirm_btn.clicked.connect(self._on_confirm)
        btn_layout.addWidget(self._confirm_btn)

        self._cancel_btn = QPushButton('取消')
        self._cancel_btn.setFixedHeight(34)
        self._cancel_btn.setMinimumWidth(80)
        self._cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._cancel_btn)

        layout.addLayout(btn_layout)

    # ── 样式 ──────────────────────────────────────────────

    def _apply_style(self):
        """应用对话框内控件样式"""
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
            QPushButton#confirmBtn {
                background: #4a90d9;
                color: #ffffff;
                border: none;
                font-weight: 600;
            }
            QPushButton#confirmBtn:hover {
                background: #357abd;
            }
            QPushButton#confirmBtn:pressed {
                background: #2a6cb5;
            }
            QPushButton#confirmBtn:disabled {
                background: #b0c4de;
                color: #ffffff;
            }
        """)

    # ── 事件 ──────────────────────────────────────────────

    def _on_browse_image(self):
        """打开图片选择对话框"""
        path, _ = QFileDialog.getOpenFileName(
            self, '选择图片', '',
            '图片文件 (*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.tif);;'
            '所有文件 (*.*)',
        )
        if not path:
            return

        ext = Path(path).suffix.lower()
        if ext not in SUPPORTED_IMAGE_FORMATS:
            QMessageBox.warning(
                self, '格式不支持',
                f'不支持 "{ext}" 格式。\n'
                f'支持的格式: {", ".join(SUPPORTED_IMAGE_FORMATS)}',
            )
            return

        self._image_path = path
        self._file_path_edit.setText(path)
        self._confirm_btn.setEnabled(True)

        # 预览缩略图
        self._show_thumbnail(path)

        # 更新推荐
        self._update_recommendation()

    def _show_thumbnail(self, image_path: str):
        """在推荐卡片中显示缩略图"""
        pix = QPixmap(image_path)
        if pix.isNull():
            return
        thumb = pix.scaled(
            120, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation,
        )
        self._preview_label.setPixmap(thumb)
        self._preview_label.setVisible(True)

    def _update_recommendation(self):
        """根据当前输入重新计算推荐位置"""
        if not self._paragraphs:
            self._recommend_label.setText('文档分析失败或文档为空')
            return

        if not self._image_path:
            self._recommend_label.setText('选择图片后自动生成推荐位置')
            return

        description = self._pos_input.text().strip()
        image_filename = Path(self._image_path).name

        # 如果有用户指令，先尝试解析
        if description:
            parsed = self._placer.parse_user_instruction(description)
            if parsed["type"] in ("number", "start", "end", "keyword"):
                try:
                    suggestion = self._resolve_from_parsed(
                        parsed, image_filename,
                    )
                    self._recommendation = suggestion
                except Exception:
                    suggestion = self._placer.suggest_position(
                        self._paragraphs, "", image_filename,
                    )
                    self._recommendation = suggestion
            else:
                suggestion = self._placer.suggest_position(
                    self._paragraphs, description, image_filename,
                )
                self._recommendation = suggestion
        else:
            suggestion = self._placer.suggest_position(
                self._paragraphs, "", image_filename,
            )
            self._recommendation = suggestion

        idx = self._recommendation["paragraph_index"]
        reason = self._recommendation["reason"]
        para = self._paragraphs[idx] if idx < len(self._paragraphs) else None

        # 显示推荐 + 上下文
        text = f'推荐位置: 第 {idx + 1} 段后面\n理由: {reason}'
        if para:
            snippet = para["text"][:80]
            text += f'\n\n段落预览: {snippet}...' if len(para["text"]) > 80 else f'\n\n段落内容: {snippet}'

        self._recommend_label.setText(text)

    def _resolve_from_parsed(self, parsed: dict, image_filename: str) -> dict:
        """根据解析后的指令获取推荐位置"""
        total = len(self._paragraphs)

        if parsed["type"] == "number":
            idx = max(0, min(parsed["value"] - 1, total - 1))
            return {"paragraph_index": idx, "reason": f"用户指定第 {idx + 1} 段"}

        if parsed["type"] == "start":
            return {"paragraph_index": 0, "reason": "用户指定文档开头"}

        if parsed["type"] == "end":
            return {"paragraph_index": total - 1, "reason": "用户指定文档末尾"}

        if parsed["type"] == "keyword":
            kws = self._placer._extract_keywords(parsed["value"], "")
            if kws:
                idx, score, matched = self._placer._find_best_paragraph(
                    self._paragraphs, kws,
                )
                if score > 0:
                    return {
                        "paragraph_index": idx,
                        "reason": f"用户指令匹配关键词（{', '.join(matched[:3])}）",
                    }
            return self._placer.suggest_position(
                self._paragraphs, "", image_filename,
            )

        return self._placer.suggest_position(
            self._paragraphs, "", image_filename,
        )

    def _on_confirm(self):
        """确认插入图片"""
        if not self._image_path:
            QMessageBox.warning(self, '提示', '请先选择图片文件')
            return

        if not self._paragraphs:
            QMessageBox.warning(self, '提示', '文档分析失败，无法插入')
            return

        try:
            description = self._pos_input.text().strip()

            output_path = self._placer.place_image(
                docx_path=self._docx_path,
                image_path=self._image_path,
                position=self._recommendation if self._recommendation.get("paragraph_index") is not None else None,
                user_instruction=description,
            )

            QMessageBox.information(
                self, '插入成功',
                f'图片已插入到文档中。\n\n'
                f'保存位置: {output_path}',
            )
            self.accept()

        except FileNotFoundError as e:
            QMessageBox.critical(self, '文件不存在', str(e))
        except ValueError as e:
            QMessageBox.warning(self, '参数错误', str(e))
        except ImportError as e:
            QMessageBox.critical(
                self, '缺少依赖',
                f'需要安装额外库: {e}\n\n请运行: pip install pillow python-docx lxml',
            )
        except Exception as e:
            logger.exception("图片插入失败")
            QMessageBox.critical(self, '插入失败', f'{type(e).__name__}: {e}')
