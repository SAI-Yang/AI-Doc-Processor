"""设置对话框"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QWidget, QFormLayout, QLineEdit, QComboBox,
    QSpinBox, QDoubleSpinBox, QPushButton, QLabel,
    QGroupBox, QTextEdit, QMessageBox, QDialogButtonBox,
)
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QFont

from app import APP_NAME, APP_VERSION
from app.config import AppConfig, LLMConfig, ProcessingConfig
from app.font_manager import get_chinese_fonts, apply_font
from PyQt5.QtWidgets import QApplication


class SettingsDialog(QDialog):
    """应用设置对话框"""

    PROVIDERS = [
        ('deepseek', 'DeepSeek'),
        ('openai', 'OpenAI'),
        ('anthropic', 'Anthropic'),
        ('custom', '自定义 (OpenAI 兼容)'),
    ]

    MODELS = {
        'deepseek': ['deepseek-chat', 'deepseek-reasoner'],
        'openai': ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'],
        'anthropic': ['claude-sonnet-4-20250514', 'claude-3-5-sonnet-latest', 'claude-3-5-haiku-latest'],
        'custom': ['custom-model'],
    }

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle('设置')
        self.setMinimumSize(520, 480)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self._build_ui()
        self._load_config()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 标签页
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_api_tab(), 'API 配置')
        self.tabs.addTab(self._build_processing_tab(), '处理配置')
        self.tabs.addTab(self._build_shortcuts_tab(), '快捷键')
        self.tabs.addTab(self._build_appearance_tab(), '外观')
        self.tabs.addTab(self._build_about_tab(), '关于')
        layout.addWidget(self.tabs)

        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.Apply).clicked.connect(self._on_apply)
        layout.addWidget(buttons)

    # ── API 配置标签页 ──────────────────────────────────

    def _build_api_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        # 提供商选择
        form = QFormLayout()
        self.provider_combo = QComboBox()
        for pid, pname in self.PROVIDERS:
            self.provider_combo.addItem(pname, pid)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        form.addRow('Provider:', self.provider_combo)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText('sk-...')
        form.addRow('API Key:', self.api_key_edit)

        self.base_url_edit = QLineEdit()
        self.base_url_edit.setPlaceholderText('https://api.deepseek.com')
        form.addRow('Base URL:', self.base_url_edit)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        form.addRow('模型:', self.model_combo)

        # 温度
        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0, 2)
        self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setDecimals(1)
        form.addRow('温度 (temperature):', self.temp_spin)

        # Max Tokens
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(64, 128000)
        self.max_tokens_spin.setSingleStep(512)
        self.max_tokens_spin.setPrefix('')
        form.addRow('最大 Token:', self.max_tokens_spin)

        layout.addLayout(form)

        # 测试连接按钮
        test_btn = QPushButton('测试连接')
        test_btn.clicked.connect(self._test_connection)
        layout.addWidget(test_btn, 0, Qt.AlignLeft)
        layout.addStretch()
        return tab

    def _on_provider_changed(self, idx: int):
        """切换 provider 时更新模型列表和建议 URL"""
        pid = self.provider_combo.itemData(idx)
        models = self.MODELS.get(pid, [])
        self.model_combo.clear()
        self.model_combo.addItems(models)
        if self.model_combo.count() > 0:
            self.model_combo.setCurrentIndex(0)

        # 建议 Base URL
        url_hints = {
            'deepseek': 'https://api.deepseek.com',
            'openai': 'https://api.openai.com/v1',
            'anthropic': 'https://api.anthropic.com',
            'custom': '',
        }
        if pid in url_hints and not self.base_url_edit.text():
            self.base_url_edit.setText(url_hints[pid])

    def _test_connection(self):
        """测试 API 连接"""
        from app.llm_client import create_client
        from app.config import LLMConfig

        cfg = LLMConfig(
            provider=self.provider_combo.currentData(),
            api_key=self.api_key_edit.text(),
            base_url=self.base_url_edit.text(),
            model=self.model_combo.currentText(),
            temperature=self.temp_spin.value(),
            max_tokens=self.max_tokens_spin.value(),
        )
        client = create_client(cfg)
        try:
            import asyncio
            result = asyncio.run(client.process_content(
                content='Hello',
                system_prompt='You are a helpful assistant.',
                user_prompt='Reply with exactly: OK',
            ))
            QMessageBox.information(self, '连接测试', f'连接成功！\n响应: {result[:100]}')
        except Exception as e:
            QMessageBox.warning(self, '连接测试', f'连接失败: {e}')

    # ── 处理配置标签页 ──────────────────────────────────

    def _build_processing_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        group = QGroupBox('处理参数')
        form = QFormLayout(group)

        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 16)
        form.addRow('最大并发数:', self.concurrent_spin)

        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(0, 10)
        form.addRow('重试次数:', self.retry_spin)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(10, 600)
        self.timeout_spin.setSuffix(' 秒')
        self.timeout_spin.setSingleStep(10)
        form.addRow('超时时间:', self.timeout_spin)

        layout.addWidget(group)

        group2 = QGroupBox('输出配置')
        form2 = QFormLayout(group2)

        self.format_combo = QComboBox()
        self.format_combo.addItems(['same_as_input', 'txt', 'docx'])
        form2.addRow('输出格式:', self.format_combo)

        layout.addWidget(group2)
        layout.addStretch()
        return tab

    # ── 快捷键标签页 ────────────────────────────────────

    def _build_shortcuts_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        shortcuts = [
            ('Ctrl+O', '添加文件'),
            ('Ctrl+T', '添加文件夹'),
            ('Ctrl+Shift+O', '添加文件夹'),
            ('Space', '预览选中文件'),
            ('F5', '开始处理'),
            ('Ctrl+P', '暂停/继续'),
            ('Escape', '取消当前处理'),
            ('Ctrl+,', '打开设置'),
            ('Ctrl+L', '清空文件列表'),
            ('Ctrl+Backspace', '移除选中文件'),
        ]

        text = '键盘快捷键\n'
        text += '─' * 40 + '\n'
        for key, desc in shortcuts:
            text += f'  {key:20s}  {desc}\n'

        edit = QTextEdit()
        edit.setPlainText(text)
        edit.setReadOnly(True)
        edit.setFont(QFont('Consolas', 11))
        layout.addWidget(edit)
        return tab

    # ── 外观标签页 ──────────────────────────────────────

    def _build_appearance_tab(self) -> QWidget:
        tab = QWidget()
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(24, 20, 24, 20)

        layout = QFormLayout()
        layout.setSpacing(16)

        # 字体选择
        font_label = QLabel('界面字体')
        font_label.setStyleSheet('font-weight: 600; font-size: 13px;')
        layout.addRow(font_label)

        self.font_combo = QComboBox()
        self.font_combo.setMinimumWidth(300)
        self._fonts = get_chinese_fonts()
        current_idx = 0
        for i, f in enumerate(self._fonts):
            label = f['name']
            if f['bundled']:
                label += f'  ● {f["style"]}'
            elif f['type'] == '系统':
                label += ' (系统)'
            self.font_combo.addItem(label, f['family'])
            if f['family'] == 'LXGW WenKai':
                current_idx = i
        self.font_combo.setCurrentIndex(current_idx)
        font_note = QLabel('💡 霞鹜文楷为打包的开源字体（18k star），其余为系统字体')
        font_note.setStyleSheet('color: #7f8c8d; font-size: 11px;')
        layout.addRow('', self.font_combo)
        layout.addRow('', font_note)

        # 预览
        preview_label = QLabel('预览效果')
        preview_label.setStyleSheet('font-weight: 600; font-size: 13px; padding-top: 8px;')
        layout.addRow(preview_label)

        self.font_preview = QTextEdit()
        self.font_preview.setMaximumHeight(100)
        self.font_preview.setPlainText(
            '这是一段字体预览文字。\n'
            'ABCDEFGHIJKLMNOPQRSTUVWXYZ\n'
            'abcdefghijklmnopqrstuvwxyz\n'
            '0123456789 !@#$%^&*()'
        )
        layout.addRow(self.font_preview)

        self.font_combo.currentIndexChanged.connect(self._on_font_changed)

        outer.addLayout(layout)
        outer.addStretch()
        return tab

    def _on_font_changed(self, idx):
        """字体选择变化时实时预览"""
        family = self.font_combo.itemData(idx)
        if family:
            font = QFont(family, 12)
            self.font_preview.setFont(font)

    # ── 关于标签页 ──────────────────────────────────────

    def _build_about_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info = QLabel(
            f'<h2>{APP_NAME}</h2>'
            f'<p>版本: {APP_VERSION}</p>'
            f'<p>基于 AI 的文档批量处理桌面工具</p>'
            f'<hr>'
            f'<p>支持格式: DOCX, PDF, TXT, Markdown</p>'
            f'<p>支持 API: DeepSeek, OpenAI, Anthropic 及兼容接口</p>'
            f'<hr>'
            f'<p style="color:#8b949e;">PyQt5 桌面应用</p>'
        )
        info.setWordWrap(True)
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)
        layout.addStretch()
        return tab

    # ── 加载 / 保存 ─────────────────────────────────────

    def _load_config(self):
        """从 config 对象加载界面值"""
        llm = self.config.llm
        proc = self.config.processing

        # API 标签：先设 provider（会触发 _on_provider_changed 更新模型列表）
        idx = self.provider_combo.findData(llm.provider)
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)
        # 再设 API Key 和 URL（覆盖 provider 切换时的默认提示）
        self.api_key_edit.setText(llm.api_key)
        self.base_url_edit.setText(llm.base_url)

        # 模型列表已在 setCurrentIndex 时通过信号更新完毕
        model_idx = self.model_combo.findText(llm.model)
        if model_idx >= 0:
            self.model_combo.setCurrentIndex(model_idx)
        else:
            self.model_combo.setCurrentText(llm.model)

        self.temp_spin.setValue(llm.temperature)
        self.max_tokens_spin.setValue(llm.max_tokens)

        # 处理标签
        self.concurrent_spin.setValue(proc.max_concurrent)
        self.retry_spin.setValue(proc.retry_count)
        self.timeout_spin.setValue(proc.timeout)
        fmt_idx = self.format_combo.findText(self.config.output.format)
        if fmt_idx >= 0:
            self.format_combo.setCurrentIndex(fmt_idx)

        # 字体标签
        font_idx = self.font_combo.findData(self.config.font_family)
        if font_idx >= 0:
            self.font_combo.setCurrentIndex(font_idx)

    def _collect_config(self) -> AppConfig:
        """从界面收集值，返回新的 AppConfig"""
        return AppConfig(
            llm=LLMConfig(
                provider=self.provider_combo.currentData(),
                api_key=self.api_key_edit.text(),
                base_url=self.base_url_edit.text().rstrip('/'),
                model=self.model_combo.currentText(),
                temperature=self.temp_spin.value(),
                max_tokens=self.max_tokens_spin.value(),
            ),
            output=self.config.output.__class__(
                format=self.format_combo.currentText(),
            ),
            processing=ProcessingConfig(
                max_concurrent=self.concurrent_spin.value(),
                retry_count=self.retry_spin.value(),
                timeout=self.timeout_spin.value(),
            ),
            font_family=self.font_combo.currentData(),
        )

    def _apply_font_globally(self, font_family: str):
        """全局应用字体：设置 QFont + 更新 QSS 覆盖"""
        try:
            app = QApplication.instance()
            if not app or not font_family:
                return
            from app.font_manager import apply_font
            apply_font(app, font_family, 10)
            # 替换 QSS 中的字体覆盖段（去除旧的 FONT_OVERRIDE，追加新的）
            current = app.styleSheet() or ''
            marker_start = '/* FONT_OVERRIDE_START */'
            marker_end = '/* FONT_OVERRIDE_END */'
            if marker_start in current:
                current = current[:current.index(marker_start)] + current[current.index(marker_end) + len(marker_end):]
            font_qss = f"""
            {marker_start}
            QLabel, QLineEdit, QTextEdit, QPlainTextEdit, QStatusBar,
            QComboBox, QListWidget, QTreeWidget {{
                font-family: "{font_family}", "Microsoft YaHei UI", "微软雅黑", sans-serif;
            }}
            QPushButton {{
                font-family: "{font_family}", "Microsoft YaHei UI", "微软雅黑", sans-serif;
                font-weight: 500;
            }}
            {marker_end}
            """
            app.setStyleSheet(current + font_qss)
        except Exception:
            pass

    def _on_apply(self):
        try:
            self.config = self._collect_config()
            self.config.save()
            self._apply_font_globally(self.font_combo.currentData())
        except Exception:
            pass

    def _on_ok(self):
        try:
            self.config = self._collect_config()
            self.config.save()
            self._apply_font_globally(self.font_combo.currentData())
            self.accept()
        except Exception:
            self.accept()

    @classmethod
    def edit_config(cls, config: AppConfig, parent=None) -> AppConfig:
        """打开设置对话框编辑配置

        Returns:
            编辑后的配置；若取消则返回原配置
        """
        dlg = cls(config, parent)
        if dlg.exec_() == QDialog.Accepted:
            return dlg.config
        return config
