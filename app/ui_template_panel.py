"""模板选择面板 - 自定义提示词编辑 + 参数配置 + 流水线"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSlider, QSpinBox,
    QPushButton, QPlainTextEdit,
    QListWidget, QListWidgetItem, QGroupBox,
    QMessageBox, QInputDialog,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from app.template_manager import TemplateManager


class TemplatePanel(QWidget):
    """模板选择面板 — 实时编辑提示词 + 参数配置 + 流水线"""

    template_changed = pyqtSignal(str, dict)  # template_id, template_data
    pipeline_changed = pyqtSignal(list)        # [step_id, ...]

    # 快速填充预设
    QUICK_FILL_PROMPTS = {
        'translate': '将以下内容翻译为英文：\n\n{text}',
        'polish': '请对以下内容进行学术润色，使其更符合学术写作规范：\n\n{text}',
        'summarize': '请对以下内容进行总结摘要，提取关键信息：\n\n{text}',
        'simplify': '请用更简单易懂的语言重新表述以下内容：\n\n{text}',
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tm = TemplateManager()
        self._custom_prompt: str = ''
        self._pipeline_ids: list[str] = []
        self._pipeline_step_prompts: dict[str, str] = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # ── 模式切换 ──
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(4)

        self.single_btn = QPushButton('\U0001f4cb 单模板')
        self.single_btn.setCheckable(True)
        self.single_btn.setChecked(True)
        self.single_btn.clicked.connect(lambda: self._switch_mode('single'))
        mode_layout.addWidget(self.single_btn)

        self.pipeline_btn = QPushButton('\U0001f517 流水线')
        self.pipeline_btn.setCheckable(True)
        self.pipeline_btn.clicked.connect(lambda: self._switch_mode('pipeline'))
        mode_layout.addWidget(self.pipeline_btn)

        layout.addLayout(mode_layout)

        # ── 大号提示词编辑区 ──
        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setPlaceholderText(
            '输入处理要求，如：将以下中文翻译为英文...'
        )
        font = QFont('Microsoft YaHei', 11)
        self.prompt_edit.setFont(font)
        self.prompt_edit.setStyleSheet('''
            QPlainTextEdit {
                padding: 10px;
                background-color: #f6f8fa;
                border: 1px solid #d0d7de;
                border-radius: 6px;
                color: #1f2328;
                selection-background-color: #0969da;
                selection-color: #ffffff;
            }
            QPlainTextEdit:focus {
                border-color: #0969da;
                background-color: #ffffff;
            }
        ''')
        self.prompt_edit.textChanged.connect(self._on_prompt_changed)
        layout.addWidget(self.prompt_edit, 1)

        # ── 快速填充按钮行 ──
        quick_btn_layout = QHBoxLayout()
        quick_btn_layout.setSpacing(4)

        btn_style = '''
            QPushButton {
                font-size: 11px; padding: 2px 8px;
                border: 1px solid #d0d7de;
                border-radius: 4px;
                background-color: #f6f8fa;
                color: #1f2328;
            }
            QPushButton:hover {
                background-color: #e8ecf0;
                border-color: #0969da;
            }
            QPushButton:pressed {
                background-color: #d0d7de;
            }
        '''

        for key, label in [
            ('translate', '翻译英文'),
            ('polish', '学术润色'),
            ('summarize', '总结摘要'),
            ('simplify', '简化'),
        ]:
            btn = QPushButton(label)
            btn.setFixedHeight(26)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(btn_style)
            btn.clicked.connect(lambda checked, k=key: self._quick_fill(k))
            quick_btn_layout.addWidget(btn)

        self.custom_fill_btn = QPushButton('自定义...')
        self.custom_fill_btn.setFixedHeight(26)
        self.custom_fill_btn.setCursor(Qt.PointingHandCursor)
        self.custom_fill_btn.setStyleSheet(btn_style)
        self.custom_fill_btn.clicked.connect(self._quick_fill_custom)
        quick_btn_layout.addWidget(self.custom_fill_btn)

        layout.addLayout(quick_btn_layout)

        # ── 参数配置 ──
        params_group = QGroupBox('参数配置')
        params_layout = QVBoxLayout(params_group)

        temp_layout = QHBoxLayout()
        temp_layout.addWidget(QLabel('温度:'))
        self.temp_slider = QSlider(Qt.Horizontal)
        self.temp_slider.setRange(0, 20)
        self.temp_slider.setValue(6)
        self.temp_slider.setToolTip('控制输出的随机性 (0=确定, 2=随机)')
        self.temp_slider.valueChanged.connect(self._on_temp_changed)
        temp_layout.addWidget(self.temp_slider)
        self.temp_label = QLabel('0.3')
        self.temp_label.setFixedWidth(32)
        temp_layout.addWidget(self.temp_label)
        params_layout.addLayout(temp_layout)

        tokens_layout = QHBoxLayout()
        tokens_layout.addWidget(QLabel('最大 Token:'))
        self.tokens_spin = QSpinBox()
        self.tokens_spin.setRange(64, 128000)
        self.tokens_spin.setValue(4096)
        self.tokens_spin.setSingleStep(512)
        self.tokens_spin.setToolTip('每次 API 调用的最大输出 Token 数')
        tokens_layout.addWidget(self.tokens_spin)
        params_layout.addLayout(tokens_layout)

        layout.addWidget(params_group)

        # ── 流水线（默认隐藏） ──
        self.pipeline_group = QGroupBox('处理流水线')
        self.pipeline_group.setVisible(False)
        pipeline_layout = QVBoxLayout(self.pipeline_group)

        self.pipeline_list = QListWidget()
        self.pipeline_list.setDragDropMode(QListWidget.InternalMove)
        self.pipeline_list.setDefaultDropAction(Qt.MoveAction)
        self.pipeline_list.setMaximumHeight(120)
        self.pipeline_list.model().rowsMoved.connect(self._on_pipeline_reordered)
        pipeline_layout.addWidget(self.pipeline_list)

        pipe_btn_layout = QHBoxLayout()
        add_pipe_btn = QPushButton('+ 添加到流水线')
        add_pipe_btn.clicked.connect(self._add_to_pipeline)
        pipe_btn_layout.addWidget(add_pipe_btn)
        clear_pipe_btn = QPushButton('清空')
        clear_pipe_btn.clicked.connect(self._clear_pipeline)
        pipe_btn_layout.addWidget(clear_pipe_btn)
        pipeline_layout.addLayout(pipe_btn_layout)

        layout.addWidget(self.pipeline_group)

    # ── 模式切换 ──

    def _switch_mode(self, mode: str):
        is_single = mode == 'single'
        self.single_btn.setChecked(is_single)
        self.pipeline_btn.setChecked(not is_single)
        self.pipeline_group.setVisible(not is_single)

    # ── 提示词编辑 ──

    def _on_prompt_changed(self):
        """提示词文本变化 -> 实时保存并触发信号"""
        self._custom_prompt = self.prompt_edit.toPlainText()
        data = {
            'id': 'custom',
            'temperature': self.temp_slider.value() / 10.0,
            'max_tokens': self.tokens_spin.value(),
            'system_prompt': '',
            'user_prompt': self._custom_prompt,
        }
        self.template_changed.emit('custom', data)

    def _quick_fill(self, key: str):
        """点击快速填充按钮 -> 追加预设提示词到文本框"""
        prompt = self.QUICK_FILL_PROMPTS.get(key)
        if not prompt:
            return
        current = self.prompt_edit.toPlainText()
        if current.strip():
            self.prompt_edit.setPlainText(current.rstrip() + '\n\n' + prompt)
        else:
            self.prompt_edit.setPlainText(prompt)

    def _quick_fill_custom(self):
        """自定义快速填充 -> 对话框输入后追加"""
        text, ok = QInputDialog.getMultiLineText(
            self, '自定义提示词',
            '输入提示词内容（用 {text} 表示文档内容占位符）:'
        )
        if not ok or not text.strip():
            return
        current = self.prompt_edit.toPlainText()
        if current.strip():
            self.prompt_edit.setPlainText(current.rstrip() + '\n\n' + text.strip())
        else:
            self.prompt_edit.setPlainText(text.strip())

    # ── 温度参数 ──

    def _on_temp_changed(self, val: int):
        self.temp_label.setText(f'{val / 10.0:.1f}')

    # ── 流水线 ──

    def _add_to_pipeline(self):
        text = self._custom_prompt.strip()
        if not text:
            QMessageBox.warning(self, '提示', '请先输入提示词')
            return
        step_id = f'pipe_step_{len(self._pipeline_ids) + 1}'
        self._pipeline_ids.append(step_id)
        self._pipeline_step_prompts[step_id] = text
        self._refresh_pipeline_list()

    def _clear_pipeline(self):
        self._pipeline_ids.clear()
        self._pipeline_step_prompts.clear()
        self._refresh_pipeline_list()

    def _on_pipeline_reordered(self):
        ids = []
        for i in range(self.pipeline_list.count()):
            item = self.pipeline_list.item(i)
            if item:
                ids.append(item.data(Qt.UserRole))
        self._pipeline_ids = ids
        self.pipeline_changed.emit(self._pipeline_ids)

    def _refresh_pipeline_list(self):
        self.pipeline_list.clear()
        for idx, pid in enumerate(self._pipeline_ids):
            prompt = self._pipeline_step_prompts.get(pid, '')
            label = (prompt[:30] + '...') if len(prompt) > 30 else (prompt if prompt else '(空)')
            item = QListWidgetItem(f'步骤 {idx + 1}: {label}')
            item.setData(Qt.UserRole, pid)
            self.pipeline_list.addItem(item)
        self.pipeline_changed.emit(self._pipeline_ids)

    # ── 对外接口 ──

    def get_selected_template(self) -> tuple[str, dict]:
        """获取当前编辑的提示词 (id, data)"""
        user = self._custom_prompt.strip()
        if not user:
            return '', {}
        return 'custom', {
            'id': 'custom',
            'temperature': self.temp_slider.value() / 10.0,
            'max_tokens': self.tokens_spin.value(),
            'system_prompt': '',
            'user_prompt': user,
        }

    def get_pipeline(self) -> list[tuple[str, dict]]:
        """获取流水线模板列表"""
        if self.pipeline_btn.isChecked() and self._pipeline_ids:
            result = []
            for pid in self._pipeline_ids:
                prompt = self._pipeline_step_prompts.get(pid, '')
                if prompt.strip():
                    result.append((pid, {
                        'id': pid,
                        'temperature': self.temp_slider.value() / 10.0,
                        'max_tokens': self.tokens_spin.value(),
                        'system_prompt': '',
                        'user_prompt': prompt,
                    }))
            return result
        # 单模板模式
        tid, data = self.get_selected_template()
        return [(tid, data)] if tid else []

    def is_pipeline_mode(self) -> bool:
        return self.pipeline_btn.isChecked() and len(self._pipeline_ids) > 1
