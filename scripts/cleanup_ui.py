"""清理 ui_main.py 中的自定义 QSS 和主题覆盖代码"""
import re

path = 'E:/Cursor/Project/projects/ai-doc-processor/app/ui_main.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 删除 CUSTOM_QSS 块（从标记到结束）
content = re.sub(
    r"# ── 浅色主题自定义 QSS（叠加于 qt-material 之上） ──────────\n\nCUSTOM_QSS = \"\"\".*?\"\"\"\n\n",
    '',
    content,
    flags=re.DOTALL
)

# 删除对已移除方法的调用
content = content.replace(
    '        # 清除 qdarktheme 全局暗色主题，替换为纯 QSS 浅色主题\n        self._clear_dark_theme()\n',
    ''
)
content = content.replace(
    '        self._fix_inline_styles()\n',
    ''
)
content = content.replace(
    '        self._apply_custom_qss()\n',
    ''
)

# 删除 _clear_dark_theme 方法定义
content = re.sub(
    r'\n    def _clear_dark_theme\(self\).*?    # ── 布局构建 ──',
    '\n    # ── 布局构建 ──',
    content,
    flags=re.DOTALL
)

# 删除 _apply_custom_qss 方法定义
content = re.sub(
    r'\n    def _apply_custom_qss\(self\).*?    # ── 布局构建 ──',
    '\n    # ── 布局构建 ──',
    content,
    flags=re.DOTALL
)

# 删除 _fix_inline_styles 方法定义
content = re.sub(
    r'\n    def _fix_inline_styles\(self\).*?    # ── 信号连接 ──',
    '\n    # ── 信号连接 ──',
    content,
    flags=re.DOTALL
)

# 删除 _restyle_template_card 方法
content = re.sub(
    r'\n    def _restyle_template_card\(self, card\).*?(?=\nclass|\n    def |\n# ──)',
    '',
    content,
    flags=re.DOTALL
)

# 删除遗留的内联样式 (panel cards, status, title 等)
# 这些由 qt-material 统一管理
remove_inline_styles = [
    "left_card.setStyleSheet('QFrame#panelCard { background: #ffffff; border: 1px solid #e1e4e8; border-radius: 10px; }')",
    "right_card.setStyleSheet('QFrame#panelCard { background: #ffffff; border: 1px solid #e1e4e8; border-radius: 10px; }')",
    "self.toolbar_status.setStyleSheet('color: #7f8c8d; font-size: 12px;')",
    "log_title.setStyleSheet('font-size: 12px; font-weight: 600; color: #2c3e50;')",
]

for s in remove_inline_styles:
    content = content.replace(s + '\n', '')

# 删除预览按钮的内联样式
content = re.sub(
    r'\n        self\.preview_copy_btn\.setStyleSheet\(.*?\n        ',
    '\n        ',
    content,
    flags=re.DOTALL
)
content = re.sub(
    r'\n        self\.preview_export_btn\.setStyleSheet\(.*?\n        ',
    '\n        ',
    content,
    flags=re.DOTALL
)
content = re.sub(
    r'\n        self\.log_clear_btn\.setStyleSheet\(.*?\n        ',
    '\n        ',
    content,
    flags=re.DOTALL
)

# 删除 log_history_tabs 的 setStyleSheet
content = re.sub(
    r'\n        log_history_tabs\.setStyleSheet\(.*?\n        ',
    '\n        ',
    content,
    flags=re.DOTALL
)

# 删除整个 _fix_inline_styles 方法
content = re.sub(
    r'\n    def _fix_inline_styles\(self\).*?\n    # ── 信号连接 ──',
    '\n    # ── 信号连接 ──',
    content,
    flags=re.DOTALL
)

# 删除 _restyle_template_card 方法
content = re.sub(
    r'\n    def _restyle_template_card\(self.*?(?=\nclass |\n    def |\n# ──)',
    '',
    content,
    flags=re.DOTALL
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Cleanup done')
