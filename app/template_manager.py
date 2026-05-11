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
        description="将中文文档翻译为英文，保留格式和风格",
        system_prompt=(
            "You are a professional translator specializing in Chinese-to-English translation. "
            "Translate the given Chinese text into natural, fluent English. "
            "Preserve the original formatting, paragraph structure, and document style. "
            "Maintain technical accuracy for domain-specific terms. "
            "Output ONLY the translation, no explanations or notes."
        ),
        user_prompt="Please translate the following Chinese text into English:\n\n{content}",
        temperature=0.3,
        max_tokens=4096,
    ),
    "en_to_zh": Template(
        name="英译中",
        description="将英文文档翻译为中文",
        system_prompt=(
            "你是一名专业翻译，负责英文到中文的翻译工作。"
            "将给定的英文文本翻译为自然流畅的中文。"
            "保留原文的格式、段落结构和文档风格。"
            "对专业术语保持准确性。"
            "只输出翻译结果，不要加注释或说明。"
        ),
        user_prompt="请将以下英文文本翻译为中文：\n\n{content}",
        temperature=0.3,
        max_tokens=4096,
    ),
    "academic_polish": Template(
        name="学术润色",
        description="润色学术写作，改进表达和语法，提升专业性",
        system_prompt=(
            "You are an academic writing assistant. Polish the given text to improve:"
            "\n1. Grammar and syntax correctness"
            "\n2. Academic tone and formality"
            "\n3. Clarity and conciseness of expression"
            "\n4. Logical flow between sentences"
            "\nMaintain the original meaning and technical accuracy."
            "Do not add new information or remove important details."
            "Output ONLY the polished text."
        ),
        user_prompt="Please polish the following academic text:\n\n{content}",
        temperature=0.3,
        max_tokens=4096,
    ),
    "general_polish": Template(
        name="通用润色",
        description="改进文法、表达和流畅度，适用于一般文本",
        system_prompt=(
            "你是一名文字润色助手。改进以下文本的语法、表达和流畅度。"
            "保持原文意思和风格不变。"
            "只输出润色后的文本，不要添加说明。"
        ),
        user_prompt="请润色以下文本：\n\n{content}",
        temperature=0.4,
        max_tokens=4096,
    ),
    "summarize": Template(
        name="摘要生成",
        description="生成文档摘要，支持长度控制",
        system_prompt=(
            "你是一名文档摘要助手。请根据以下文本生成简洁、全面的摘要。"
            "摘要应涵盖核心观点和主要结论。"
            "使用客观中立的语言。"
            "只输出摘要内容。"
        ),
        user_prompt="请为以下文本生成摘要：\n\n{content}",
        temperature=0.3,
        max_tokens=1024,
    ),
    "key_points": Template(
        name="要点提取",
        description="提取关键点和行动项",
        system_prompt=(
            "你是一名要点提取助手。从以下文本中提取关键点和行动项。"
            "用简洁的条目形式输出。"
            "关键点每项一句话。"
            "行动项标注 [行动项] 前缀。"
            "只输出提取结果。"
        ),
        user_prompt="请从以下文本中提取关键点和行动项：\n\n{content}",
        temperature=0.3,
        max_tokens=2048,
    ),
    "format_normalize": Template(
        name="格式规范化",
        description="统一术语、修正格式、规范化表达",
        system_prompt=(
            "你是一名文本格式化助手。规范化以下文本："
            "\n1. 统一术语（同一概念使用同一词汇）"
            "\n2. 确保标点符号使用正确"
            "\n3. 统一数字和单位格式"
            "\n4. 修正明显的大小写错误"
            "\n保留原文内容和段落结构。只输出规范化后的文本。"
        ),
        user_prompt="请规范化以下文本：\n\n{content}",
        temperature=0.2,
        max_tokens=4096,
    ),
    "expand": Template(
        name="扩写",
        description="在原有内容基础上扩展细节和解释",
        system_prompt=(
            "你是一名内容扩写助手。扩展以下文本："
            "\n1. 为关键概念提供更详细的解释"
            "\n2. 补充相关背景信息"
            "\n3. 添加适当的例子或论据"
            "\n保持原文的核心观点和结构。"
            "不要偏离主题。只输出扩写后的文本。"
        ),
        user_prompt="请扩写以下文本，补充更多细节：\n\n{content}",
        temperature=0.5,
        max_tokens=4096,
    ),
    "simplify": Template(
        name="简化",
        description="将复杂内容简化为易懂的版本",
        system_prompt=(
            "你是一名内容简化助手。将以下文本简化为更易懂的版本。"
            "\n1. 用更简单的词汇替换复杂术语"
            "\n2. 缩短长句"
            "\n3. 保留核心信息"
            "\n4. 适当使用类比帮助理解"
            "\n保持信息准确性。只输出简化后的文本。"
        ),
        user_prompt="请简化以下文本，使其更易于理解：\n\n{content}",
        temperature=0.3,
        max_tokens=4096,
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

    def render(self, template_id: str, content: str) -> tuple[str, str, float, int]:
        """渲染模板，生成 system_prompt 和 user_prompt

        Args:
            template_id: 模板 ID
            content: 文档内容

        Returns:
            (system_prompt, user_prompt, temperature, max_tokens)

        Raises:
            KeyError: 模板不存在
        """
        tpl = self.get(template_id)
        if tpl is None:
            raise KeyError(f"模板 '{template_id}' 不存在")
        user_prompt = tpl.user_prompt.replace("{content}", content)
        return tpl.system_prompt, user_prompt, tpl.temperature, tpl.max_tokens

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
