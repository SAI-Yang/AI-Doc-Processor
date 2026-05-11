"""
AI 文档批处理工具 - 核心处理引擎 + GUI 共享常量
"""

__version__ = "0.1.0"

# ── 文件状态 ──────────────────────────────────────────────
FILE_PENDING = 0
FILE_PROCESSING = 1
FILE_DONE = 2
FILE_FAILED = 3

STATUS_SYMBOLS = {FILE_PENDING: '○', FILE_PROCESSING: '●', FILE_DONE: '✓', FILE_FAILED: '✗'}
STATUS_COLORS = {
    FILE_PENDING: '#8b949e',
    FILE_PROCESSING: '#58a6ff',
    FILE_DONE: '#3fb950',
    FILE_FAILED: '#f85149',
}
STATUS_TEXTS = {
    FILE_PENDING: '待处理',
    FILE_PROCESSING: '处理中',
    FILE_DONE: '已完成',
    FILE_FAILED: '失败',
}

# ── 应用信息 ──────────────────────────────────────────────
APP_NAME = 'AI 文档批处理工具'
APP_VERSION = '1.0.0'
APP_ORG = 'AIDocProcessor'

# ── GUI 模板元数据（与 template_manager 中的 ID 对应）────
TEMPLATE_METADATA = {
    'zh_to_en':         {'icon': '⇄', 'category': '翻译'},
    'en_to_zh':         {'icon': '⇄', 'category': '翻译'},
    'academic_polish':  {'icon': '✎', 'category': '润色'},
    'general_polish':   {'icon': '✎', 'category': '润色'},
    'summarize':        {'icon': '§', 'category': '处理'},
    'key_points':       {'icon': '▪', 'category': '处理'},
    'format_normalize': {'icon': '☰', 'category': '处理'},
    'expand':           {'icon': '⊕', 'category': '处理'},
    'simplify':         {'icon': '▽', 'category': '处理'},
    'custom':           {'icon': '✚', 'category': '自定义'},
}

# 类别排序
CATEGORY_ORDER = ['翻译', '润色', '处理', '自定义']

# ── 文件类型 ──────────────────────────────────────────────
FILE_FILTER_ALL = (
    '所有支持的文件 (*.docx *.pdf *.txt *.md);;'
    'Word 文档 (*.docx);;'
    'PDF 文档 (*.pdf);;'
    '文本文件 (*.txt);;'
    'Markdown (*.md);;'
    '所有文件 (*.*)'
)
SUPPORTED_EXTENSIONS = {'.docx', '.pdf', '.txt', '.md'}
