"""文档处理技能引擎 - 保障中文文档正确处理

每次调用自动执行：
1. 编码检测（UTF-8/GBK/GB2312）
2. 全文档处理（不分块或带上下文的分块）
3. 输出编码验证
4. 乱码自动修复
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# ── 常见中文字符范围 ──────────────────────────────────────
CJK_RANGES = [
    (0x4E00, 0x9FFF),   # CJK 统一表意文字
    (0x3400, 0x4DBF),   # CJK 扩展A
    (0x2B820, 0x2CEAF), # CJK 扩展E
    (0xF900, 0xFAFF),   # CJK 兼容表意文字
    (0x3000, 0x303F),   # CJK 符号和标点
    (0xFF00, 0xFFEF),   # 全角 ASCII 和标点
]

def is_garbled(text: str, threshold: float = 0.15) -> bool:
    """检测文本是否乱码

    如果非CJK、非ASCII、非常见标点的字符比例超过阈值，判定为乱码。
    """
    if not text:
        return False
    total = len(text)
    bad = 0
    for ch in text:
        code = ord(ch)
        # 允许 ASCII
        if 0x20 <= code <= 0x7E:
            continue
        # 允许 CJK
        in_cjk = False
        for start, end in CJK_RANGES:
            if start <= code <= end:
                in_cjk = True
                break
        if in_cjk:
            continue
        # 允许常见标点
        if ch in '，。、；：？！""''（）【】《》—…· \t\n\r':
            continue
        bad += 1
    ratio = bad / total
    return ratio > threshold

def detect_encoding(text: str) -> str:
    """检测文本编码问题"""
    # 检查是否有常见乱码模式
    garbled_patterns = [
        (r'å\x9f\xba|æ\x9c\xac|ç\x9a\x84|ä\xba\x86|ä¸\x80', 'utf8_bytes_shown_as_latin1'),
        (r'&#[0-9]{2,6};', 'html_entities'),
        (r'\\u[0-9a-fA-F]{4}', 'unicode_escapes'),
        (r'ð\x9f|ð\x90|ð\x98', 'emoji_bytes'),
    ]
    issues = []
    for pattern, name in garbled_patterns:
        if re.search(pattern, text):
            issues.append(name)
    return issues

def repair_garbled(text: str) -> str:
    """尝试修复常见乱码"""
    # 修复将UTF-8字节解释为Latin-1的情况
    try:
        repaired = text.encode('latin-1').decode('utf-8', errors='ignore')
        if not is_garbled(repaired) and len(repaired) > len(text) * 0.5:
            return repaired
    except:
        pass
    return text

# ── 编码安全提示词 ──────────────────────────────────────

ENCODING_SAFETY_PROMPT = r"""【重要】输出要求：
1. 使用和输入完全相同的语言和编码
2. 不要输出乱码、HTML实体、Unicode转义序列
3. 中文标点使用全角（，。、；：？！）
4. 英文和数字使用半角
5. 【关键】保留原文每一个字，不删减、不遗漏任何内容
6. 【关键】保留原文所有标题、编号、格式、段落结构，完全不改动
7. 【关键】禁止使用任何 Markdown 符号（**、*、#、`、>、---、```等）
8. 不要添加原文没有的内容、注释或说明
9. 不要输出"修改说明"或任何额外文字
10. 【关键】严格保留原文中的空格、缩进和特殊排版格式（包括封面字间空格如"实 验 报 告"）
11. 如果原文无明显问题，保持原样输出
12. 确保所有字符正确显示，不要使用\uXXXX转义
13. 输出纯文本，不要任何格式标记"""

# ── 上下文分块处理 ──────────────────────────────────────

def build_context_chunks(text: str, max_chars: int = 8000, overlap: int = 500):
    """构建带上下文的分块

    每块包含前一块末尾的 overlap 字符作为上下文，
    保证 LLM 在每块中都有完整的语境。
    """
    if len(text) <= max_chars:
        return [(0, text, '')]

    chunks = []
    start = 0
    chunk_index = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        # 在段落边界截断
        if end < len(text):
            # 找上一个换行
            newline_pos = text.rfind('\n', start, end)
            if newline_pos > start + max_chars // 2:
                end = newline_pos + 1

        chunk_text = text[start:end]
        # 前一块的末尾作为上下文
        context = ''
        if chunk_index > 0:
            ctx_start = max(0, start - overlap)
            context = text[ctx_start:start]

        chunks.append((chunk_index, chunk_text, context))
        chunk_index += 1
        start = end

    return chunks

# ── Markdown 剥离 ──────────────────────────────────────────

def strip_markdown(text: str) -> str:
    """彻底移除所有 Markdown 格式符号"""
    # 移除 **粗体**（必须成对出现，中间有内容）
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    # 移除 *斜体*（只匹配两端都不是英文数字的情况，保留 a*b 等乘式）
    text = re.sub(r'(?<![a-zA-Z0-9])\*([a-zA-Z一-鿿]+)\*(?![a-zA-Z0-9])', r'\1', text)
    # 移除 __下划线__
    text = re.sub(r'__([^_]+?)__', r'\1', text)
    # 移除 _斜体_（只匹配两端都不是英文单词字符的情况，保留 H_hp 等变量名）
    text = re.sub(r'(?<![a-zA-Z0-9])_([a-zA-Z一-鿿]+)_(?![a-zA-Z0-9])', r'\1', text)
    # 移除 `行内代码`
    text = re.sub(r'`(.+?)`', r'\1', text)
    # 移除代码块 ```...```
    text = re.sub(r'```[\s\S]*?```', '', text)
    # 移除 #hash# 标签（行中或行首）
    text = re.sub(r'#([^#\s]+)#', r'\1', text)
    # 移除行首标题标记
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # 移除单独 # 符号（前后有空格的情况）
    text = re.sub(r'\s#\s', ' ', text)
    # 移除引用标记
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)
    # 移除行中 > 引用符号
    text = re.sub(r'\s>\s', ' ', text)
    # 移除分隔线
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    # 移除无序列表标记
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    # 移除有序列表标记
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    return text.strip()


# ── 输出清洗 ──────────────────────────────────────────────

def clean_output(text: str) -> str:
    """清洗LLM输出，移除可能的污染物"""
    if not text:
        return text

    # 移除常见的 LLM 思考产物
    text = re.sub(r'^[思考|分析|理解|好的]+\s*[：:\n]', '', text.strip())

    # 移除可能的 markdown 代码块标记
    text = re.sub(r'^```[\w]*\n', '', text)
    text = re.sub(r'\n```$', '', text)

    # 剥离所有 Markdown 格式符号
    text = strip_markdown(text)

    # 修复全角英文和数字
    def fullwidth_to_halfwidth(s):
        result = []
        for ch in s:
            code = ord(ch)
            if 0xFF01 <= code <= 0xFF5E:
                result.append(chr(code - 0xFEE0))
            elif code == 0x3000:
                result.append(' ')
            else:
                result.append(ch)
        return ''.join(result)

    text = fullwidth_to_halfwidth(text)

    # 乱码检测与修复
    if is_garbled(text):
        logger.warning('检测到输出可能包含乱码，尝试修复')
        text = repair_garbled(text)

    return text.strip()

# ── 文档处理技能 ──────────────────────────────────────

class DocProcessingSkill:
    """文档处理技能 - 保障每次处理的编码和质量

    使用方式:
        skill = DocProcessingSkill()
        result = await skill.process(text, template)
        # result 保证是干净的、完整的文本
    """

    def __init__(self, llm_client):
        self.llm = llm_client

    async def process(self, content: str, system_prompt: str, user_prompt: str) -> str:
        """处理文档内容，保障编码正确

        步骤:
        1. 编码检测
        2. 上下文分块（仅对长文档）
        3. 逐块处理（带上下文）
        4. 输出清洗
        5. 编码验证
        """
        # 1. 编码检测
        encoding_issues = detect_encoding(content)
        if encoding_issues:
            logger.warning(f'输入文本存在编码问题: {encoding_issues}')
            content = repair_garbled(content)

        # 2. 补充编码安全提示词
        enhanced_system = system_prompt + '\n\n' + ENCODING_SAFETY_PROMPT

        # 3. 分块处理
        chunks = build_context_chunks(content)
        results = []

        for idx, chunk_text, context in chunks:
            # 构建带上下文的 user_prompt
            if context:
                full_user = f'【上文内容】\n{context}\n\n【当前需要处理的部分】\n{chunk_text}'
            else:
                full_user = chunk_text

            # 替换模板中的 {content}
            prompt = user_prompt.replace('{content}', full_user)
            if '{text}' in prompt:
                prompt = prompt.replace('{text}', full_user)

            try:
                result = await self.llm.process_content(
                    content=full_user,
                    system_prompt=enhanced_system,
                    user_prompt=prompt,
                )
                # 清洗
                result = clean_output(result)

                # 编码验证
                if is_garbled(result):
                    logger.warning(f'第 {idx+1} 块输出可能存在乱码，尝试修复')
                    result = repair_garbled(result)

                results.append(result)
            except Exception as e:
                logger.error(f'第 {idx+1} 块处理失败: {e}')
                results.append(chunk_text)  # 失败时保留原文

        # 4. 合并结果
        final = '\n\n'.join(results)
        final = clean_output(final)

        # 5. 最终验证
        if is_garbled(final):
            logger.error('最终输出仍存在乱码')
            # 尝试终极修复
            final = repair_garbled(final)

        return final
