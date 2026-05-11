"""处理模板管理模块

内置 9 种处理模板，支持自定义模板从 JSON 文件加载。
每个模板包含系统提示词、用户提示词模板、建议温度和最大 Token 数。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 自定义模板默认目录
DEFAULT_TEMPLATES_DIR = Path.home() / ".ai-doc-processor" / "templates"


@dataclass
class Template:
    """处理模板"""
    name: str
    description: str
    system_prompt: str  # 系统提示词
    user_prompt: str    # 用户提示词模板，用 {content} 占位
    temperature: float  # 建议温度
    max_tokens: int     # 建议最大 Token


# ── 内置模板 ──────────────────────────────────────────────

_BUILTIN_TEMPLATES: dict[str, Template] = {
    "zh_to_en": Template(
        name="中译英",
        description="专业学术中译英，保留术语和格式",
        system_prompt=(
            "You are a professional academic translator specializing in Chinese-to-English translation. "
            "Your task is to produce publication-ready English from Chinese text.\n\n"
            "Requirements:\n"
            "1. Terminology: Use standard English academic terms. First occurrence of key terms should include the Chinese original in parentheses if ambiguous.\n"
            "2. Style: Formal academic English, appropriate for journal publication. Avoid colloquialisms.\n"
            "3. Sentence structure: Convert Chinese topic-comment structures to English subject-verb-object. Split overly long sentences.\n"
            "4. Formatting: Preserve original paragraph breaks, headings, and list structures exactly.\n"
            "5. Conciseness: Eliminate redundant modifiers common in Chinese academic writing (e.g., '积极' '大力' '有效').\n"
            "6. Articles and prepositions: Pay special attention to English articles (a/an/the) and prepositions, which are often misused by Chinese speakers.\n\n"
            "Output ONLY the translated text. No explanations, no notes, no alternative translations."
        ),
        user_prompt=(
            "Please translate the following Chinese academic text into fluent, publication-ready English. "
            "Maintain all technical terms and preserve the original structure.\n\n"
            "--- Original Chinese ---\n{content}"
        ),
        temperature=0.25,
        max_tokens=8192,
    ),
    "en_to_zh": Template(
        name="英译中",
        description="专业英译中，地道中文表达，术语准确",
        system_prompt=(
            "你是一名专业学术翻译，负责英文到中文的翻译工作。\n\n"
            "要求：\n"
            "1. 术语处理：专业术语采用学界通用译名，首次出现的英文术语在括号中标注原文，例如「卷积神经网络（CNN）」\n"
            "2. 句式转换：将英文长句拆解为符合中文表达习惯的短句，避免欧化句式（过多「的」字结构、被动语态）\n"
            "3. 语态处理：英文被动语态转换为中文主动语态（e.g., 'it was found that' → '研究发现'）\n"
            "4. 风格要求：使用正式书面中文，避免口语化表达，但也不过度文言\n"
            "5. 格式保留：完全保留原文的段落划分、标题层级和列表结构\n"
            "6. 文化适配：英文中的文化特定表达需做本地化处理，而非直译\n\n"
            "只输出翻译结果，不要添加注释或说明。"
        ),
        user_prompt="请将以下英文文本翻译为专业、地道的中文：\n\n{content}",
        temperature=0.25,
        max_tokens=8192,
    ),
    "academic_polish": Template(
        name="学术润色",
        description="仅优化语言表达，不改标题和结构",
        system_prompt=(
            "你是一名学术文本润色助手。你的任务是对学术文本进行语言层面的优化。\n\n"
            "【严格遵守】\n"
            "1. 只修改语言表达（语法、用词、流畅度），不改内容\n"
            "2. 保留原文所有标题、编号、格式、段落结构，完全不改动\n"
            "3. 保留原文中可能存在的格式标记（如加粗文字、编号列表等）\n"
            "4. 不要添加原文没有的内容、注释或说明\n"
            "5. 不要给文章分段、加标题或重新组织结构\n"
            '6. 不要输出"修改说明"或任何额外文字\n'
            "7. 只输出润色后的原文，不增不减\n\n"
            "润色方向：\n"
            "- 修正语法错误和不通顺的表达\n"
            "- 用更准确的学术用语替换口语化表达\n"
            "- 优化句式结构，使表达更清晰\n"
            "- 确保术语一致性\n"
            "如果原文无明显问题，保持原样输出。"
        ),
        user_prompt="请润色以下学术文本，只改语言表达，不改任何标题和结构：\n\n{content}",
        temperature=0.25,
        max_tokens=8192,
    ),
    "general_polish": Template(
        name="通用润色",
        description="全面改进文法、表达和流畅度，保留原意",
        system_prompt=(
            "你是一名文字润色专家。对以下文本进行全面优化：\n\n"
            "1. 修正所有语病、错别字和标点错误\n"
            "2. 优化表达流畅度，消除生硬或不通顺的句子\n"
            "3. 调整句式结构，使表达更自然\n"
            "4. 统一术语和表达方式\n"
            "5. 适当精简冗余表达\n\n"
            "原则：保持原文风格和语气，不改变原意。\n"
            "如果原文无明显问题，可保持基本不变。\n"
            "只输出润色后的文本。"
        ),
        user_prompt="请润色以下文本，改进其表达质量：\n\n{content}",
        temperature=0.3,
        max_tokens=8192,
    ),
    "summarize": Template(
        name="摘要生成",
        description="结构化摘要：总览+核心要点，自动适配文本长度",
        system_prompt=(
            "你是一名多语言文献研究专家和中文表达大师。请根据文本长度自动适配摘要粒度。\n\n"
            "输出分为两部分，严格按以下结构：\n"
            "第一部分是总览摘要（120到200字），用一段话概括全文核心内容，包括研究或文档目的、主要方法或论点、关键结论。\n\n"
            "第二部分是核心要点（3到8条），每条使用四字短语作为标题，后跟一句话解释说明。\n"
            "例如：先用四字短语概括技术架构，再一句话说明架构方式；先用四字短语概括实验验证，再一句话说明方法和结果。\n\n"
            "质量检查标准：\n"
            "1. 理解准确性：摘要是否准确反映原文？\n"
            "2. 信息完整性：关键数据和结论是否全部涵盖？\n"
            "3. 表达地道性：中文是否自然流畅？\n"
            "4. 逻辑清晰度：要点间是否有逻辑关系？\n\n"
            "只输出摘要内容，不要加额外说明。"
        ),
        user_prompt="请为以下内容生成高质量摘要：\n\n{content}",
        temperature=0.3,
        max_tokens=2048,
    ),
    "key_points": Template(
        name="要点提取",
        description="结构化提取：关键发现+数据结论+行动建议",
        system_prompt=(
            "你是一名信息提取专家。从以下文本中提取结构化的关键信息。\n\n"
            "输出分为几个部分，只提取内容中实际包含的信息：\n\n"
            "核心发现部分：每行用一句话概括一项最重要的发现或结论。\n\n"
            "关键数据部分：列出提取到的具体数据指标和数值，如果没有则跳过。\n\n"
            "结论与建议部分：列出作者或文档得出的主要结论，以及建议的行动项。\n\n"
            "关键词部分：列出3到5个关键词，用逗号分隔。\n\n"
            "如果内容不涉及某类信息，可跳过该分类。只输出提取结果。"
        ),
        user_prompt="请从以下文本中提取结构化的关键信息：\n\n{content}",
        temperature=0.2,
        max_tokens=2048,
    ),
    "expand": Template(
        name="扩写",
        description="基于原文扩展：补充细节+背景+例证",
        system_prompt=(
            "你是一名内容扩写专家。在保留原文核心观点和结构的基础上，扩展以下文本：\n\n"
            "扩写方向：\n"
            "1. 概念阐释：为关键术语和概念提供更详细的解释（1-2句）\n"
            "2. 背景补充：添加相关的背景信息或上下文，帮助读者理解\n"
            "3. 例证支撑：为主论点添加具体的例子、数据或引用（如有）\n"
            "4. 逻辑衔接：在段落之间添加过渡句，增强论证的连贯性\n"
            "5. 结论深化：对原有结论进行适度延伸，指出其意义或影响\n\n"
            "约束：\n"
            "- 保持原文的核心观点和结论不变\n"
            "- 新增内容须与原文风格一致\n"
            "- 避免无意义的重复或啰嗦\n"
            "- 不偏离主题\n\n"
            "输出扩写后的完整文本。"
        ),
        user_prompt="请扩展以下文本，补充更多细节和例证：\n\n{content}",
        temperature=0.5,
        max_tokens=8192,
    ),
    "simplify": Template(
        name="简化",
        description="专业降维：复杂内容→通俗易懂，保留核心信息",
        system_prompt=(
            "你是一名科普作家，擅长将专业内容转化为通俗易懂的表达。\n\n"
            "简化要求：\n"
            "1. 词汇替换：用日常用语替换专业术语（如 '神经网络' → 可简单解释为 '一种模拟人脑的计算模型'）\n"
            "2. 句子简化：将长句（>30字）拆分为短句，每句只传达一个信息点\n"
            "3. 比喻辅助：适当使用类比和比喻帮助理解抽象概念（如 'DNA如同生物的蓝图'）\n"
            "4. 保留核心：只保留最关键的信息，删除次要细节和数据\n"
            "5. 逻辑清晰：确保简化后的内容因果关系明确\n\n"
            "约束：保持信息准确性，不因简化而曲解原意。\n\n"
            "输出简化后的文本。"
        ),
        user_prompt="请将以下内容简化为通俗易懂的版本：\n\n{content}",
        temperature=0.3,
        max_tokens=4096,
    ),
    "generate_caption": Template(
        name="图片标题生成",
        description="基于图片描述和文档上下文，生成图片/图表的标题",
        system_prompt=(
            "You are a figure caption generator. Based on the image description and "
            "the document context provided, generate a concise and descriptive caption "
            "for the figure or table.\n"
            "Rules:\n"
            "1. Captions should be one sentence (10-25 words)\n"
            "2. Use 'Figure X:' or 'Table X:' prefix when appropriate\n"
            "3. Describe what is shown, not what can be inferred\n"
            "4. Match the academic tone of the surrounding document\n"
            "Output ONLY the caption text, no explanations."
        ),
        user_prompt=(
            "Document context:\n{document_context}\n\n"
            "Image description:\n{content}\n\n"
            "Generate a caption:"
        ),
        temperature=0.3,
        max_tokens=128,
    ),
    "image_description": Template(
        name="图片内容描述",
        description="用文字详细描述图片中的内容和关键信息",
        system_prompt=(
            "你是一名图片内容描述助手。基于用户提供的图片描述，生成结构化的文字说明。\n"
            "内容应包括：\n"
            "1. 图片类型（流程图/数据图/示意图/照片等）\n"
            "2. 主要元素和结构\n"
            "3. 关键数据或结论（如适用）\n"
            "4. 与文档上下文的关系\n"
            "使用客观、准确的语言。只输出描述文本。"
        ),
        user_prompt=(
            "文档上下文：{document_context}\n\n"
            "图片描述：{content}\n\n"
            "请描述图片内容："
        ),
        temperature=0.4,
        max_tokens=512,
    ),
}


# ── 模板管理 ──────────────────────────────────────────────

class TemplateManager:
    """处理模板管理器

    管理内置模板和自定义模板的加载、查询。
    """

    def __init__(self, custom_dir: Optional[Path] = None):
        self._custom_dir = custom_dir or DEFAULT_TEMPLATES_DIR
        self._custom_templates: dict[str, Template] = {}
        self._load_custom()

    # ── 查询 ──────────────────────────────────────────

    def list_templates(self) -> list[dict]:
        """列出所有可用模板（内置 + 自定义）

        Returns:
            模板信息列表，每项含 name, description, is_builtin
        """
        result = []
        for name, tpl in _BUILTIN_TEMPLATES.items():
            result.append({
                "id": name,
                "name": tpl.name,
                "description": tpl.description,
                "is_builtin": True,
                "temperature": tpl.temperature,
                "max_tokens": tpl.max_tokens,
            })
        for name, tpl in self._custom_templates.items():
            result.append({
                "id": name,
                "name": tpl.name,
                "description": tpl.description,
                "is_builtin": False,
                "temperature": tpl.temperature,
                "max_tokens": tpl.max_tokens,
            })
        return result

    def get(self, template_id: str) -> Optional[Template]:
        """获取指定 ID 的模板

        Args:
            template_id: 模板 ID（内置模板的 key 或自定义模板文件名不带后缀）

        Returns:
            Template 实例，未找到返回 None
        """
        if template_id in _BUILTIN_TEMPLATES:
            return _BUILTIN_TEMPLATES[template_id]
        return self._custom_templates.get(template_id)

    def render(self, template_id: str, content: str,
               **context) -> tuple[str, str, float, int]:
        """渲染模板，生成 system_prompt 和 user_prompt

        Args:
            template_id: 模板 ID
            content: 文档内容（替换 {content} 和 {text} 占位符）
            **context: 额外上下文变量（替换 {key} 占位符）

        Returns:
            (system_prompt, user_prompt, temperature, max_tokens)

        Raises:
            KeyError: 模板不存在
        """
        tpl = self.get(template_id)
        if tpl is None:
            raise KeyError(f"模板 '{template_id}' 不存在")
        # 替换主内容占位符
        user_prompt = tpl.user_prompt.replace("{content}", content).replace("{text}", content)
        # 替换额外上下文（如 {document_context}）
        for key, value in context.items():
            placeholder = "{" + key + "}"
            if placeholder in user_prompt:
                user_prompt = user_prompt.replace(placeholder, str(value))
        return tpl.system_prompt, user_prompt, tpl.temperature, tpl.max_tokens

    def render_custom_with_optimizer(
        self,
        user_input: str,
        content: str,
        doc_type: str = "general",
        content_preview: str = "",
    ) -> tuple[str, str, float, int]:
        """使用优化器处理用户输入，生成完整提示词

        用于"自定义模板"场景：用户输入模糊需求（如"翻译成英文"），
        经优化器转化为精确的结构化提示词后再传给 LLM。

        Args:
            user_input: 用户的原始处理要求
            content: 文档完整内容
            doc_type: 文档类型 (general/academic/technical/business)
            content_preview: 文档内容前 200 字（用于术语检测和语言判断）

        Returns:
            (system_prompt, user_prompt, temperature, max_tokens)
        """
        from .prompt_optimizer import optimize_prompt, build_system_prompt

        optimized = optimize_prompt(
            user_input,
            doc_type=doc_type,
            content_preview=content_preview,
        )
        system_prompt = build_system_prompt(optimized)
        user_prompt = f"{optimized}\n\n{content}"
        return system_prompt, user_prompt, 0.3, 4096

    def get_default_template_id(self) -> str:
        """获取默认模板 ID（第一个内置模板）"""
        return next(iter(_BUILTIN_TEMPLATES))

    # ── 自定义模板管理 ─────────────────────────────────

    def add_custom(self, template_id: str, template: Template) -> None:
        """添加或更新自定义模板

        Args:
            template_id: 模板 ID
            template: Template 实例
        """
        self._custom_templates[template_id] = template
        self._save_custom(template_id, template)
        logger.info("自定义模板已保存: %s", template_id)

    def remove_custom(self, template_id: str) -> bool:
        """删除自定义模板

        Args:
            template_id: 模板 ID

        Returns:
            是否成功删除
        """
        if template_id in _BUILTIN_TEMPLATES:
            logger.warning("不能删除内置模板: %s", template_id)
            return False

        if template_id in self._custom_templates:
            del self._custom_templates[template_id]
            file_path = self._custom_dir / f"{template_id}.json"
            if file_path.exists():
                file_path.unlink()
            logger.info("自定义模板已删除: %s", template_id)
            return True
        return False

    def export_template(self, template_id: str, path: Path) -> None:
        """导出模板到 JSON 文件

        Args:
            template_id: 模板 ID
            path: 导出路径
        """
        tpl = self.get(template_id)
        if tpl is None:
            raise KeyError(f"模板 '{template_id}' 不存在")
        data = {"id": template_id, **asdict(tpl)}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("模板已导出到 %s", path)

    def import_template(self, path: Path) -> str:
        """从 JSON 文件导入模板

        Args:
            path: JSON 文件路径

        Returns:
            导入的模板 ID
        """
        data = json.loads(path.read_text(encoding="utf-8"))
        template_id = data.pop("id", path.stem)
        template = Template(
            name=data.get("name", template_id),
            description=data.get("description", ""),
            system_prompt=data.get("system_prompt", ""),
            user_prompt=data.get("user_prompt", ""),
            temperature=float(data.get("temperature", 0.3)),
            max_tokens=int(data.get("max_tokens", 4096)),
        )
        self.add_custom(template_id, template)
        logger.info("模板已导入: %s -> %s", path, template_id)
        return template_id

    # ── 内部方法 ──────────────────────────────────────

    def _load_custom(self) -> None:
        """从自定义目录加载所有 JSON 模板"""
        if not self._custom_dir.exists():
            return
        for fpath in sorted(self._custom_dir.glob("*.json")):
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
                template_id = fpath.stem
                self._custom_templates[template_id] = Template(
                    name=data.get("name", template_id),
                    description=data.get("description", ""),
                    system_prompt=data.get("system_prompt", ""),
                    user_prompt=data.get("user_prompt", ""),
                    temperature=float(data.get("temperature", 0.3)),
                    max_tokens=int(data.get("max_tokens", 4096)),
                )
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("加载自定义模板失败 %s: %s", fpath, e)

    def _save_custom(self, template_id: str, template: Template) -> None:
        """保存单个自定义模板到 JSON 文件"""
        self._custom_dir.mkdir(parents=True, exist_ok=True)
        file_path = self._custom_dir / f"{template_id}.json"
        data = asdict(template)
        file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
