"""配置文件管理模块

提供 API 配置、处理模板配置的保存和加载功能。
支持 JSON 格式的配置读写，带字段验证和默认值。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 默认配置文件路径
DEFAULT_CONFIG_DIR = Path.home() / ".ai-doc-processor"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.json"


@dataclass
class LLMConfig:
    """LLM API 配置"""
    provider: str = "deepseek"  # 提供商：deepseek / openai / anthropic / ollama 等
    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    temperature: float = 0.3
    max_tokens: int = 4096


@dataclass
class OutputConfig:
    """输出配置"""
    format: str = "same_as_input"  # same_as_input / txt / docx
    encoding: str = "utf-8"


@dataclass
class ProcessingConfig:
    """处理配置"""
    max_concurrent: int = 3
    retry_count: int = 2
    timeout: int = 120  # 单次 API 调用超时（秒）


@dataclass
class AppConfig:
    """应用配置"""
    llm: LLMConfig = field(default_factory=LLMConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    font_family: str = "LXGW WenKai"  # 字体选择，默认霞鹜文楷
    output_dir: str = ""  # 输出目录，空表示使用桌面/AI-处理结果

    @classmethod
    def default(cls) -> "AppConfig":
        """创建默认配置"""
        return cls()

    def save(self, path: Optional[Path] = None) -> Path:
        """保存配置到 JSON 文件

        Args:
            path: 保存路径，默认为 ~/.ai-doc-processor/config.json

        Returns:
            保存的文件路径
        """
        save_path = path or DEFAULT_CONFIG_PATH
        save_path.parent.mkdir(parents=True, exist_ok=True)

        data = asdict(self)
        save_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        logger.info("配置已保存到 %s", save_path)
        return save_path

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "AppConfig":
        """从 JSON 文件加载配置，文件不存在时返回默认配置

        Args:
            path: 配置文件路径，默认 ~/.ai-doc-processor/config.json

        Returns:
            加载后的配置对象
        """
        load_path = path or DEFAULT_CONFIG_PATH
        if not load_path.exists():
            logger.info("配置文件 %s 不存在，使用默认配置", load_path)
            return cls.default()

        try:
            data = json.loads(load_path.read_text(encoding="utf-8"))
            llm_data = data.get("llm", {})
            output_data = data.get("output", {})
            processing_data = data.get("processing", {})

            return cls(
                llm=LLMConfig(
                    provider=llm_data.get("provider", "deepseek"),
                    api_key=llm_data.get("api_key", ""),
                    base_url=llm_data.get("base_url", "https://api.deepseek.com"),
                    model=llm_data.get("model", "deepseek-chat"),
                    temperature=llm_data.get("temperature", 0.3),
                    max_tokens=llm_data.get("max_tokens", 4096),
                ),
                output=OutputConfig(
                    format=output_data.get("format", "same_as_input"),
                    encoding=output_data.get("encoding", "utf-8"),
                ),
                processing=ProcessingConfig(
                    max_concurrent=processing_data.get("max_concurrent", 3),
                    retry_count=processing_data.get("retry_count", 2),
                    timeout=processing_data.get("timeout", 120),
                ),
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("配置文件解析失败: %s，使用默认配置", e)
            return cls.default()

    def validate(self) -> list[str]:
        """验证配置有效性，返回错误信息列表

        Returns:
            错误信息列表，为空表示配置有效
        """
        errors: list[str] = []

        # LLM 配置验证
        if not self.llm.api_key:
            errors.append("API 密钥未设置，请在配置中填入 api_key")
        if not self.llm.base_url:
            errors.append("API 地址未设置")
        if not self.llm.model:
            errors.append("模型名称未设置")
        if not (0 <= self.llm.temperature <= 2):
            errors.append("temperature 应在 0~2 范围内")
        if self.llm.max_tokens < 64:
            errors.append("max_tokens 不应小于 64")

        # 处理配置验证
        if self.processing.max_concurrent < 1:
            errors.append("max_concurrent 不应小于 1")
        if self.processing.retry_count < 0:
            errors.append("retry_count 不应为负数")
        if self.processing.timeout < 10:
            errors.append("timeout 不应小于 10 秒")

        return errors
