"""模板选择面板 - 卡片式模板列表 + 参数配置 + 流水线"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QFrame, QLabel, QSlider, QSpinBox, QDoubleSpinBox,
    QPushButton, QTextEdit, QComboBox, QListWidget,
    QListWidgetItem, QGroupBox, QSizePolicy, QToolButton,
    QMessageBox, QSplitter,
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QPainter, QColor, QBrush, QPen, QPalette

from app import TEMPLATE_METADATA, CATEGORY_ORDER
from app.template_manager import TemplateManager


class TemplateCard(QFrame):
    """模板卡片"""

    clicked = pyqtSignal(object)  # template_id

    def __init__(self, template_id: str, name: str, desc: str,
                 icon: str, category: str, parent=None):
        super().__init__(parent)
        self.template_id = template_id
        self._selected = False
        self._build_ui(name, desc, icon, category)

    def _build_ui(self, name: str, desc: str, icon: str, category: str):
        self.setFixedHeight(72)
        self.setCursor(Qt.PointingHandCursor)
        self.setFrameShape(QFrame.StyledPanel)
        self.setToolTip(f'{name}\n{desc}')

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        # 图标
        icon_label = QLabel(icon)
        icon_label.setFont(QFont('Segoe UI', 20))
        icon_label.setFixedWidth(36)
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        # 文字
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        name_label = QLabel(name)
        name_label.setStyleSheet('font-size: 13px; font-weight: bold; color: #e6edf3;')
        text_layout.addWidget(name_label)

        cat_label = QLabel(category)
        cat_label.setStyleSheet('font-size: 11px; color: #58a6ff;')
        text_layout.addWidget(cat_label)

        desc_label = QLabel(desc)
        desc_label.setStyleSheet('font-size: 11px; color: #8b949e;')
        desc_label.setWordWrap(True)
        desc_label.setMaximumHeight(32)
        text_layout.addWidget(desc_label)

        layout.addLayout(text_layout, 1)

        self._update_style()

    def _update_style(self):
        if self._selected:
            self.setStyleSheet(
                'TemplateCard {'
                '  background-color: #1f6feb22;'
                '  border: 2px solid #1f6feb;'
                '  border-radius: 8px;'
                '}'
            )
        else:
            self.setStyleSheet(
                'TemplateCard {'
                '  background-color: #161b22;'
                '  border: 1px solid #30363d;'
                '  border-radius: 8px;'
                '}'
                'TemplateCard:hover {'
                '  background-color: #1c2128;'
                '  border-color: #8b949e;'
                '}'
            )

    def set_selected(self, sel: bool):
        self._selected = sel
        self._update_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.template_id)
        super().mousePressEvent(event)


class TemplatePanel(QWidget):
    """模板选择面板"""

    template_changed = pyqtSignal(str, dict)  # template_id, template_data
    pipeline_changed = pyqtSignal(list)        # [template_id, ...]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tm = TemplateManager()
        self._selected_id: str = ''
        self._pipeline_ids: list[str] = []
        self._cards: dict[str, TemplateCard] = {}
        self._build_ui()
        self._load_templates()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 模式切换
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(4)

        self.single_btn = QPushButton('📋 单模板')
        self.single_btn.setCheckable(True)
        self.single_btn.setChecked(True)
        self.single_btn.clicked.connect(lambda: self._switch_mode('single'))
        mode_layout.addWidget(self.single_btn)

        self.pipeline_btn = QPushButton('🔗 流水线')
        self.pipeline_btn.setCheckable(True)
        self.pipeline_btn.clicked.connect(lambda: self._switch_mode('pipeline'))
        mode_layout.addWidget(self.pipeline_btn)

        layout.addLayout(mode_layout)

        # 模板卡片列表 (滚动区域)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)

        self.card_container = QWidget()
        self.card_layout = QVBoxLayout(self.card_container)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.setSpacing(4)
        self.card_layout.addStretch()
        scroll.setWidget(self.card_container)
        layout.addWidget(scroll, 1)

        # 流水线列表 (默认隐藏)
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
        add_selected_btn = QPushButton('+ 添加选中到流水线')
        add_selected_btn.clicked.connect(self._add_selected_to_pipeline)
        pipe_btn_layout.addWidget(add_selected_btn)
        clear_pipe_btn = QPushButton('清空')
        clear_pipe_btn.clicked.connect(self._clear_pipeline)
        pipe_btn_layout.addWidget(clear_pipe_btn)
        pipeline_layout.addLayout(pipe_btn_layout)

        layout.addWidget(self.pipeline_group)

        # 参数配置
        params_group = QGroupBox('参数配置')
        params_layout = QVBoxLayout(params_group)

        # 温度
        temp_layout = QHBoxLayout()
        temp_layout.addWidget(QLabel('温度:'))
        self.temp_slider = QSlider(Qt.Horizontal)
        self.temp_slider.setRange(0, 20)
        self.temp_slider.setValue(6)  # 0.3
        self.temp_slider.setToolTip('控制输出的随机性 (0=确定, 2=随机)')
        self.temp_slider.valueChanged.connect(self._on_temp_changed)
        temp_layout.addWidget(self.temp_slider)
        self.temp_label = QLabel('0.3')
        self.temp_label.setFixedWidth(32)
        temp_layout.addWidget(self.temp_label)
        params_layout.addLayout(temp_layout)

        # Max Tokens
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

        # 自定义模板编辑
        self.custom_group = QGroupBox('自定义提示词')
        self.custom_group.setVisible(False)
        custom_layout = QVBoxLayout(self.custom_group)

        self.system_prompt_edit = QTextEdit()
        self.system_prompt_edit.setPlaceholderText('系统提示词 (system prompt)...')
        self.system_prompt_edit.setMaximumHeight(80)
        custom_layout.addWidget(QLabel('系统提示词:'))
        custom_layout.addWidget(self.system_prompt_edit)

        self.user_prompt_edit = QTextEdit()
        self.user_prompt_edit.setPlaceholderText('用户提示词模板，用 {text} 表示文档内容...')
        self.user_prompt_edit.setMaximumHeight(80)
        custom_layout.addWidget(QLabel('用户提示词:'))
        custom_layout.addWidget(self.user_prompt_edit)

        apply_custom_btn = QPushButton('应用自定义')
        apply_custom_btn.clicked.connect(self._apply_custom)
        custom_layout.addWidget(apply_custom_btn)

        layout.addWidget(self.custom_group)

    def _load_templates(self):
        """加载模板卡片"""
        # 清空旧卡片（保留 stretch）
        while self.card_layout.count() > 1:
            item = self.card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._cards.clear()

        # 按类别分组
        templates = self._tm.list_templates()
        categorized = {cat: [] for cat in CATEGORY_ORDER}
        for t in templates:
            tid = t['id']
            meta = TEMPLATE_METADATA.get(tid, {'icon': '●', 'category': '其他'})
            cat = meta.get('category', '其他')
            if cat in categorized:
                categorized[cat].append((tid, t, meta))
            else:
                categorized.setdefault('其他', []).append((tid, t, meta))

        # 类别标题 + 卡片
        for cat in CATEGORY_ORDER:
            items = categorized.get(cat, [])
            if not items:
                continue

            # 类别分隔
            sep = QLabel(cat)
            sep.setStyleSheet(
                'font-size: 11px; color: #58a6ff; padding: 6px 0 2px 0; '
                'border-bottom: 1px solid #21262d;'
            )
            self.card_layout.addWidget(sep)

            for tid, t, meta in items:
                card = TemplateCard(
                    tid, t['name'], t['description'],
                    meta.get('icon', '●'), cat,
                )
                card.clicked.connect(self._on_card_clicked)
                self._cards[tid] = card
                self.card_layout.addWidget(card)

        # 默认选中第一个
        if self._cards and not self._selected_id:
            first_id = list(self._cards.keys())[0]
            self._select_template(first_id)

    def _switch_mode(self, mode: str):
        is_single = mode == 'single'
        self.single_btn.setChecked(is_single)
        self.pipeline_btn.setChecked(not is_single)

        self.pipeline_group.setVisible(not is_single)
        if is_single:
            # 恢复单模板模式
            self.custom_group.setVisible(self._selected_id == 'custom')

    def _on_card_clicked(self, template_id: str):
        self._select_template(template_id)

    def _select_template(self, template_id: str):
        """选中模板"""
        # 取消旧选中
        if self._selected_id and self._selected_id in self._cards:
            self._cards[self._selected_id].set_selected(False)

        self._selected_id = template_id

        if template_id in self._cards:
            self._cards[template_id].set_selected(True)

        # 显示/隐藏自定义编辑
        self.custom_group.setVisible(template_id == 'custom')

        # 获取模板数据
        tpl = self._tm.get(template_id)
        if tpl:
            self.temp_slider.setValue(int(tpl.temperature * 10))
            self.tokens_spin.setValue(tpl.max_tokens)
            data = {
                'id': template_id,
                'temperature': tpl.temperature,
                'max_tokens': tpl.max_tokens,
                'system_prompt': tpl.system_prompt,
                'user_prompt': tpl.user_prompt,
            }
            self.template_changed.emit(template_id, data)

    def _on_temp_changed(self, val: int):
        temp = val / 10.0
        self.temp_label.setText(f'{temp:.1f}')

    # ── 流水线 ──────────────────────────────────────────

    def _add_selected_to_pipeline(self):
        if self._selected_id and self._selected_id not in self._pipeline_ids:
            self._pipeline_ids.append(self._selected_id)
            self._refresh_pipeline_list()

    def _clear_pipeline(self):
        self._pipeline_ids.clear()
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
        for tid in self._pipeline_ids:
            tpl = self._tm.get(tid)
            name = tpl.name if tpl else tid
            item = QListWidgetItem(f'{name}')
            item.setData(Qt.UserRole, tid)
            self.pipeline_list.addItem(item)
        self.pipeline_changed.emit(self._pipeline_ids)

    # ── 自定义模板 ──────────────────────────────────────

    def _apply_custom(self):
        system = self.system_prompt_edit.toPlainText().strip()
        user = self.user_prompt_edit.toPlainText().strip()

        if not user:
            QMessageBox.warning(self, '提示', '请输入用户提示词')
            return

        data = {
            'id': 'custom',
            'temperature': self.temp_slider.value() / 10.0,
            'max_tokens': self.tokens_spin.value(),
            'system_prompt': system,
            'user_prompt': user,
        }
        self.template_changed.emit('custom', data)

    # ── 对外接口 ────────────────────────────────────────

    def get_selected_template(self) -> tuple[str, dict]:
        """获取当前选中的模板 (id, data)"""
        tpl = self._tm.get(self._selected_id)
        if not tpl:
            return '', {}

        if self._selected_id == 'custom':
            system = self.system_prompt_edit.toPlainText().strip()
            user = self.user_prompt_edit.toPlainText().strip()
        else:
            system = tpl.system_prompt
            user = tpl.user_prompt

        return self._selected_id, {
            'id': self._selected_id,
            'temperature': self.temp_slider.value() / 10.0,
            'max_tokens': self.tokens_spin.value(),
            'system_prompt': system,
            'user_prompt': user,
        }

    def get_pipeline(self) -> list[tuple[str, dict]]:
        """获取流水线模板列表"""
        if self.pipeline_btn.isChecked() and self._pipeline_ids:
            result = []
            for tid in self._pipeline_ids:
                tpl = self._tm.get(tid)
                if tpl:
                    result.append((tid, {
                        'id': tid,
                        'temperature': tpl.temperature,
                        'max_tokens': tpl.max_tokens,
                        'system_prompt': tpl.system_prompt,
                        'user_prompt': tpl.user_prompt,
                    }))
            return result
        # 单模板模式
        tid, data = self.get_selected_template()
        return [(tid, data)] if tid else []

    def is_pipeline_mode(self) -> bool:
        return self.pipeline_btn.isChecked() and len(self._pipeline_ids) > 1
