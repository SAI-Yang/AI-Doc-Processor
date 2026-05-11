"""字体管理 - 加载打包字体 + 系统字体检测"""

from pathlib import Path
from PyQt5.QtGui import QFontDatabase, QFont

FONTS_DIR = Path(__file__).parent.parent / 'fonts'

# 打包的开源字体
BUNDLED_FONTS = {
    '霞鹜文楷 (LXGW WenKai)': {
        'file': 'LXGWWenKai-Regular.ttf',
        'style': '楷体·手写',
        'type': '开源 (OFL 1.1)',
    },
}

def load_bundled_fonts() -> dict:
    """加载 fonts/ 目录下的打包字体，返回 {显示名: 字体族名}"""
    result = {}
    if not FONTS_DIR.exists():
        return result
    try:
        for name, info in BUNDLED_FONTS.items():
            ttf_path = FONTS_DIR / info['file']
            if ttf_path.exists():
                font_id = QFontDatabase.addApplicationFont(str(ttf_path))
                if font_id != -1:
                    families = QFontDatabase.applicationFontFamilies(font_id)
                    if families:
                        result[name] = families[0]
    except Exception:
        pass
    return result

def get_chinese_fonts() -> list[dict]:
    """获取所有支持中文的字体列表"""
    bundled = load_bundled_fonts()
    fonts = []

    # 打包字体优先显示
    for name, family in bundled.items():
        info = BUNDLED_FONTS.get(name, {})
        fonts.append({
            'name': name,
            'family': family,
            'type': info.get('type', '打包'),
            'style': info.get('style', ''),
            'bundled': True,
        })

    # 系统常见中文字体
    system_chinese = {
        '微软雅黑': 'Microsoft YaHei',
        '微软雅黑 UI': 'Microsoft YaHei UI',
        '宋体': 'SimSun',
        '黑体': 'SimHei',
        '楷体': 'KaiTi',
        '等线': 'DengXian',
        '思源黑体': 'Noto Sans SC',
        '思源宋体': 'Noto Serif SC',
    }
    db = QFontDatabase()
    for name, family in system_chinese.items():
        if name not in bundled.values() and family in db.families():
            fonts.append({
                'name': name,
                'family': family,
                'type': '系统',
                'style': '',
                'bundled': False,
            })

    # 扫描其他系统中文字体
    for family in sorted(db.families()):
        if family not in [f['family'] for f in fonts]:
            # 简单检测是否支持中文（包含 CJK 字体的常见命名）
            lower = family.lower()
            if any(kw in lower for kw in ['cjk', 'chinese', 'sc', 'hk', 'tw', 'jp',
                                           'song', 'hei', 'kai', 'ming', 'fang',
                                           '黑', '宋', '楷', '明', '仿', '圆',
                                           'noto', 'wenquan', '文泉', '思源']):
                if family not in [f['family'] for f in fonts]:
                    fonts.append({
                        'name': family,
                        'family': family,
                        'type': '系统',
                        'style': '',
                        'bundled': False,
                    })

    return fonts

def apply_font(app, family: str, size: int = 10):
    """全局应用指定字体"""
    font = QFont(family, size)
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)
