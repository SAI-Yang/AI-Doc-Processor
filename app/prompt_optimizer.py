"""提示词优化模块

将用户输入的模糊需求自动优化为清晰、结构化的提示词。
纯规则引擎，通过关键词匹配和意图识别实现，不调用外部 API。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ── 规则定义 ──────────────────────────────────────────────────

@dataclass
class Rule:
    """优化规则

    Attributes:
        id: 规则唯一标识
        category: 规则类别（用于同类去重）
        keywords: 触发关键词列表（匹配任意一个即触发）
        template: 优化后的提示词模板
        priority: 优先级（同 category 内更高者胜出）
    """
    id: str
    category: str
    keywords: list[str]
    template: str
    priority: int = 0


_RULES: list[Rule] = [
    # ── 翻译 → 英文 ──
    # "翻译"兜底 → 译成英文（优先级低）
    Rule(
        id="translate_en",
        category="translate",
        keywords=[
            "译成英文", "译为英文", "翻译为英文", "翻成英文",
            "translate into english", "translate to english",
            "翻译",  # 兜底："翻译"无方向时默认译成英文
        ],
        template="请将以下内容翻译为英文，保持专业术语准确，语气正式，保留原文格式和段落结构",
        priority=10,
    ),
    # ── 翻译 → 中文 ──
    # 必须含"成中文"/"为中文"/"to chinese"才触发，优先级高于 translate_en
    Rule(
        id="translate_zh",
        category="translate",
        keywords=[
            "翻译成中文", "译成中文", "翻译为中文", "翻成中文", "译为中文",
            "translate into chinese", "translate to chinese",
        ],
        template="请将以下内容翻译为简体中文，使用自然地道的中文表达，保留专业术语的英文原名对照",
        priority=11,
    ),
    # ── 通用润色 ──
    Rule(
        id="polish_general",
        category="polish",
        keywords=["润色", "改一下", "polish", "改进", "优化表达"],
        template="请对以下内容进行语言润色：修正语法错误、优化表达流畅度、保持原有风格和语气",
        priority=10,
    ),
    # ── 学术润色 ──
    # 含"学术/论文"时优先级高于通用润色
    Rule(
        id="polish_academic",
        category="polish",
        keywords=["学术", "论文", "academic", "thesis", "paper", "期刊"],
        template="请以学术写作标准优化以下内容：提升用词正式度、修正语法、优化句式结构、保持学术严谨性",
        priority=20,
    ),
    # ── 英文润色 ──
    # 明确指定英文时使用
    Rule(
        id="polish_english",
        category="polish",
        keywords=["英文润色", "英语润色", "english polish", "english editing",
                  "polish english", "英文校对"],
        template="Please polish the following English text: correct grammar errors, "
                 "improve vocabulary choice, enhance sentence flow, maintain academic tone",
        priority=15,
    ),
    # ── 摘要生成 ──
    Rule(
        id="summarize",
        category="summarize",
        keywords=["摘要", "总结", "summary", "summarize", "概括", "总结一下"],
        template="请提取以下内容的核心要点，生成简洁的摘要（保留关键数据、结论和主要论点）",
        priority=10,
    ),
    # ── 扩写 ──
    Rule(
        id="expand",
        category="expand",
        keywords=["扩写", "扩展", "展开", "expand", "elaborate", "详细说明"],
        template="请在原文基础上扩展细节和论述，补充相关解释和例子，保持风格一致",
        priority=10,
    ),
    # ── 简化 / 通俗化 ──
    Rule(
        id="simplify",
        category="simplify",
        keywords=["简化", "通俗", "易懂", "简单点", "simplify", "plain", "通俗易懂"],
        template="请将以下内容简化为通俗易懂的版本，用简单的语言解释专业概念",
        priority=10,
    ),
    # ── 正式 / 公文风格 ──
    Rule(
        id="formal",
        category="style",
        keywords=["正式", "公文", "官方", "书面语", "formal", "公文体", "公函"],
        template="请将以下内容改写为正式书面语风格，使用规范用语，语气庄重",
        priority=10,
    ),
    # ── 幽默 / 活泼风格 ──
    Rule(
        id="humor",
        category="style",
        keywords=["幽默", "活泼", "轻松", "funny", "humor", "casual", "有趣"],
        template="请将以下内容改写为轻松活泼的风格，适当加入幽默表达，但仍保持信息完整",
        priority=10,
    ),
    # ── 要点提取 ──
    Rule(
        id="extract",
        category="extract",
        keywords=["要点", "提炼", "key points", "提取要点", "概括要点", "重点"],
        template="请提取以下内容的关键要点，以列表形式输出，每个要点一行",
        priority=10,
    ),
]


# ── 专有名词检测模式 ─────────────────────────────────────────

# 用于检测文档中需要保护的专有名词、缩写和技术术语
_TERM_PATTERNS: list[re.Pattern] = [
    re.compile(r'(?<![a-zA-Z])[A-Z]{2,}(?![a-zA-Z])'),              # 全大写缩写：API, DSP, PDF, STM
    re.compile(r'\b[A-Z][a-z]+[A-Z]\w*\b'),                          # 驼峰式名称：DeepSeek, OpenAI
    re.compile(r'\b\d+(?:\.\d+)?\s*(?:Hz|MHz|GHz|KB|MB|GB|TB|px|dpi|mm|cm)\b', re.IGNORECASE),  # 数值+单位
]

# 常见缩写表（小写形式匹配）
_COMMON_ABBREVIATIONS: set[str] = {
    "api", "dsp", "json", "html", "css", "pdf", "docx", "txt", "yaml", "xml",
    "stm", "fft", "fir", "pid", "adc", "dma", "pwm", "gpio", "spi", "i2c",
    "usart", "oled", "lcd", "ram", "rom", "cpu", "gpu", "fpga", "soc",
    "http", "https", "url", "uri", "ssh", "ssl", "tls", "tcp", "udp", "ip",
    "gui", "cli", "sdk", "ide", "vim", "npm", "pip", "conda", "git", "svn",
    "ai", "ml", "dl", "nn", "cnn", "rnn", "lstm", "gan", "transformer",
    "matlab", "python", "cuda", "opencl", "vulkan", "directx", "opengl",
}

# 模板前缀（用于组合时剥离）
_STRIP_PREFIXES: list[str] = [
    "请将以下内容",
    "请对以下内容",
    "请提取以下内容",
    "请在原文基础上",
]

# 语气适配映射
_TONE_MAP: dict[str, str] = {
    "academic": "请保持学术严谨性和正式语气。",
    "technical": "请保持技术准确性和专业性。",
    "business": "请使用专业商务语气，简洁高效。",
}


# ── 核心函数 ──────────────────────────────────────────────────

def detect_document_language(text: str) -> str:
    """检测文档主要语言

    Args:
        text: 文档内容（通常取前 200 字即可）

    Returns:
        "zh" 或 "en"
    """
    if not text.strip():
        return "zh"

    chinese_chars = len(re.findall(r'[一-鿿]', text))
    english_chars = len(re.findall(r'[a-zA-Z]', text))

    return "zh" if chinese_chars >= english_chars else "en"


def extract_key_requirements(text: str) -> list[str]:
    """从用户输入中提取关键词要求

    Args:
        text: 用户原始输入

    Returns:
        匹配到的规则 ID 列表（按优先级降序）
    """
    if not text.strip():
        return []

    matched = _match_rules(text)
    return [rule.id for rule in matched]


def optimize_prompt(
    user_input: str,
    doc_type: str = "general",
    content_preview: str = "",
) -> str:
    """用户输入优化引擎

    基于规则引擎，将模糊的用户需求优化为清晰、结构化的提示词。

    Args:
        user_input: 用户输入的原始处理要求
        doc_type: 文档类型 (general / academic / technical / business)
        content_preview: 文档内容前 200 字（用于检测语言和内容类型）

    Returns:
        优化后的提示词
    """
    if not user_input.strip():
        return _build_fallback_prompt(doc_type)

    # 规则匹配
    matched_rules = _match_rules(user_input)

    if not matched_rules:
        return _build_fallback_prompt(doc_type, user_input)

    # 按类别去重（同类保留优先级最高的）
    unique_rules = _deduplicate_by_category(matched_rules)

    # 组合模板
    prompt = _combine_templates(unique_rules)

    # 应用额外优化策略
    prompt = _apply_extra_strategies(prompt, doc_type, content_preview, matched_rules)

    return prompt


def build_system_prompt(optimized_prompt: str) -> str:
    """构建完整的 system prompt（含格式保护指令）

    Args:
        optimized_prompt: optimize_prompt 的输出

    Returns:
        完整的 system prompt
    """
    return (
        f"{optimized_prompt}\n\n"
        "请完全保留原文的段落结构、标题层级、列表格式。"
    )


# ── 内部辅助 ─────────────────────────────────────────────────

def _match_rules(text: str) -> list[Rule]:
    """将用户输入与规则进行关键词匹配

    Args:
        text: 用户输入

    Returns:
        匹配到的规则列表（按优先级降序）
    """
    matched: list[Rule] = []
    matched_ids: set[str] = set()

    for rule in _RULES:
        for kw in rule.keywords:
            if kw in text:
                if rule.id not in matched_ids:
                    matched.append(rule)
                    matched_ids.add(rule.id)
                break

    matched.sort(key=lambda r: r.priority, reverse=True)
    return matched


def _deduplicate_by_category(rules: list[Rule]) -> list[Rule]:
    """同类规则只保留优先级最高的一个"""
    best: dict[str, Rule] = {}
    for rule in rules:
        cat = rule.category
        if cat not in best or rule.priority > best[cat].priority:
            best[cat] = rule
    # 保持优先级降序
    return sorted(best.values(), key=lambda r: r.priority, reverse=True)


def _strip_prefix(template: str) -> str:
    """去掉模板中的常见前缀（用于规则组合）"""
    result = template
    for prefix in _STRIP_PREFIXES:
        if result.startswith(prefix):
            result = result[len(prefix):].strip()
            break
    if result.endswith("。"):
        result = result[:-1]
    return result


def _combine_templates(rules: list[Rule]) -> str:
    """将多条规则的模板组合成一条提示词"""
    if len(rules) == 1:
        return rules[0].template

    # 检测 translate + 其他操作的组合
    translate_rules = [r for r in rules if r.category == "translate"]
    other_rules = [r for r in rules if r.category != "translate"]

    if translate_rules and other_rules:
        # 顺序处理：先翻译，再对结果进行其他操作
        trans_core = _strip_prefix(translate_rules[0].template)
        other_parts = [_strip_prefix(r.template) for r in other_rules]
        other_joined = "；".join(other_parts)
        label = "翻译结果" if len(other_rules) == 1 else "以上结果"
        return f"请先将以下内容{trans_core}。然后对{label}{other_joined}。"

    if len(rules) >= 2 and all(r.category == "translate" for r in rules):
        # 多条翻译规则同时匹配（理论上不会发生，兜底处理）
        return rules[0].template

    # 非翻译组合：所有指令并行作用于同一内容
    parts = [rules[0].template]
    for r in rules[1:]:
        text = r.template
        if text.startswith("请"):
            text = text[1:]  # 去掉"请"，用"同时请"连接
        parts.append(text)
    return "。同时，请".join(parts)


def _build_fallback_prompt(
    doc_type: str = "general",
    original_input: str = "",
) -> str:
    """生成兜底提示词（无规则匹配或空输入时使用）"""
    tone = _TONE_MAP.get(doc_type, "")

    if not original_input:
        if tone:
            return f"请对以下内容进行处理，{tone}"
        return "请根据文档内容进行适当处理。"

    if tone:
        return f"请根据以下要求对文档内容进行处理：{original_input}，{tone}"

    return f"请根据文档内容和以下要求进行处理：{original_input}"


def _detect_terms(text: str) -> list[str]:
    """检测文本中的专有名词和技术术语

    Args:
        text: 文档内容

    Returns:
        检测到的术语列表（去重排序）
    """
    terms: set[str] = set()

    # 正则匹配
    for pattern in _TERM_PATTERNS:
        for match in pattern.finditer(text):
            term = match.group().strip()
            if term and not term.isdigit():
                terms.add(term)

    # 常见缩写匹配
    words = re.findall(r'[a-zA-Z][a-zA-Z0-9]*', text)
    for word in words:
        if word.lower() in _COMMON_ABBREVIATIONS:
            terms.add(word)

    return sorted(terms)


def _apply_extra_strategies(
    prompt: str,
    doc_type: str,
    content_preview: str,
    matched_rules: list[Rule],
) -> str:
    """应用额外优化策略：语气适配、术语保护、长度提示、语言适配"""
    extras: list[str] = []

    # 1. 语气适配
    tone = _TONE_MAP.get(doc_type)
    if tone:
        extras.append(tone)

    # 2. 术语保护
    if content_preview:
        terms = _detect_terms(content_preview)
        if terms:
            term_str = "、".join(terms[:10])  # 最多保护 10 个
            extras.append(f"请保留以下专有名词和技术术语的原样：{term_str}。")

    # 3. 长度提示
    if len(content_preview) > 2000:
        extras.append("文档内容较长，建议分段处理以保持输出质量。")

    # 4. 语言适配
    if content_preview:
        lang = detect_document_language(content_preview)
        is_english_instruction = any("Please" in r.template for r in matched_rules)
        if lang == "en" and not is_english_instruction:
            extras.append("检测到文档为英文，请保持英文输出。")

    if not extras:
        return prompt

    prompt = prompt.rstrip("。") + "。" + "\n\n" + "\n".join(extras)
    return prompt


# ── 测试 ──────────────────────────────────────────────────────

def test_optimizer():
    """运行优化器测试"""
    tests = [
        "翻译成英文",
        "帮我润色一下这篇论文",
        "写个摘要",
        "用简单点的话说",
        "帮我把这篇文章改成正式公文风格",
        "",
        "先翻译成中文，再润色一遍",
    ]

    print("=" * 60)
    print("  提示词优化引擎测试")
    print("=" * 60)

    for t in tests:
        result = optimize_prompt(t)
        print(f"\n输入: {t!r}")
        print(f"输出: {result}")
        print()

    # 测试 build_system_prompt
    print("=" * 60)
    print("  build_system_prompt 示例")
    print("=" * 60)
    system = build_system_prompt(optimize_prompt("翻译成英文"))
    print(system)
    print()

    # 测试 extract_key_requirements
    print("=" * 60)
    print("  extract_key_requirements 示例")
    print("=" * 60)
    for t in ["翻译成英文", "帮我润色一下这篇论文", "先翻译成中文，再润色一遍"]:
        reqs = extract_key_requirements(t)
        print(f"  输入: {t!r} -> {reqs}")

    # 测试 detect_document_language
    print()
    print("=" * 60)
    print("  detect_document_language 示例")
    print("=" * 60)
    print(f"  中文: {detect_document_language('这是一段中文文本')}")
    print(f"  英文: {detect_document_language('This is English text.')}")
    print(f"  中英混合: {detect_document_language('API 接口返回 JSON 数据')}")


if __name__ == "__main__":
    test_optimizer()
