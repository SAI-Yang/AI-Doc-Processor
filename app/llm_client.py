"""LLM API 调用客户端

支持 OpenAI 兼容 API（DeepSeek、通义千问等）和 Anthropic API。
提供流式输出、自动重试（指数退避）、Token 计数、超时处理。
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Callable, Optional

from .config import LLMConfig

logger = logging.getLogger(__name__)

# ── Token 估算 ────────────────────────────────────────────

# 中文字符约 1.5 token，英文约 1 token per 4 chars
_CHINESE_CHAR_RANGE = range(0x4E00, 0x9FFF + 1)


def estimate_tokens(text: str) -> int:
    """粗略估算文本的 token 数量（不依赖 tiktoken）

    中文字符按 1.5 token 估算，英文按 word 数 * 1.3 估算。
    用于分块决策，不需要精确到个位数。

    Args:
        text: 输入文本

    Returns:
        估算的 token 数
    """
    chinese_chars = sum(1 for c in text if ord(c) in _CHINESE_CHAR_RANGE)
    other_chars = len(text) - chinese_chars
    # 中文约 1.5 token/字，英文约 4 字符/token
    return int(chinese_chars * 1.5 + other_chars / 4) + 1


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """使用 tiktoken 精确计数 token

    若 tiktoken 不可用或模型不在表中，回退到估算。

    Args:
        text: 输入文本
        model: 模型名称

    Returns:
        token 数量
    """
    try:
        import tiktoken
        try:
            encoding = tiktoken.encoding_for_model(model)
            return len(encoding.encode(text))
        except KeyError:
            # 模型不在 tiktoken 表中，用 cl100k_base
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
    except ImportError:
        return estimate_tokens(text)


# ── API 异常 ──────────────────────────────────────────────

class LLMError(Exception):
    """LLM API 调用错误基类"""


class RateLimitError(LLMError):
    """限流错误"""


class TimeoutError(LLMError):
    """超时错误"""


class AuthenticationError(LLMError):
    """认证错误"""


class BadRequestError(LLMError):
    """请求参数错误"""


# ── 客户端抽象 ────────────────────────────────────────────

class BaseLLMClient(ABC):
    """LLM 客户端抽象基类"""

    def __init__(self, config: LLMConfig):
        self.config = config

    async def process_content(
        self,
        content: str,
        system_prompt: str,
        user_prompt: str,
        on_chunk: Optional[Callable[[str], None]] = None,
        retry_count: int = 2,
    ) -> str:
        """处理文档内容，返回 AI 处理结果

        Args:
            content: 待处理的原始文本（此实现中忽略，user_prompt 已含 content）
            system_prompt: 系统提示词
            user_prompt: 用户提示词（已渲染含 content）
            on_chunk: 可选的回调，每次收到流式块时调用
            retry_count: 最大重试次数

        Returns:
            AI 处理后的文本
        """
        return await self._retry_call(
            system_prompt, user_prompt,
            on_chunk=on_chunk,
            retry_count=retry_count,
        )

    @abstractmethod
    async def _call_api(
        self,
        system_prompt: str,
        user_prompt: str,
        on_chunk: Optional[Callable[[str], None]] = None,
    ) -> str:
        """实际的 API 调用，子类实现"""
        ...

    async def _retry_call(
        self,
        system_prompt: str,
        user_prompt: str,
        on_chunk: Optional[Callable[[str], None]] = None,
        retry_count: int = 2,
    ) -> str:
        """带自动重试和指数退避的 API 调用

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            on_chunk: 流式回调
            retry_count: 最大重试次数

        Returns:
            AI 响应文本
        """
        last_error: Optional[Exception] = None
        for attempt in range(retry_count + 1):
            try:
                return await self._call_api(system_prompt, user_prompt, on_chunk)
            except RateLimitError:
                # 限流：等待指数退避
                wait = 2 ** (attempt + 1)
                logger.warning(
                    "API 限流，第 %d 次重试，等待 %ds", attempt + 1, wait
                )
                await asyncio.sleep(wait)
                last_error = RateLimitError("API 限流，已重试失败")
            except (TimeoutError, asyncio.TimeoutError):
                wait = 2 ** (attempt + 1)
                logger.warning(
                    "API 超时，第 %d 次重试，等待 %ds", attempt + 1, wait
                )
                await asyncio.sleep(wait)
                last_error = TimeoutError("API 超时，已重试失败")
            except AuthenticationError:
                # 认证错误不重试
                raise
            except BadRequestError:
                # 请求参数错误不重试
                raise
            except Exception as e:
                # 其他错误重试
                wait = 2 ** (attempt + 1)
                logger.warning(
                    "API 调用异常 (%s)，第 %d 次重试，等待 %ds",
                    e, attempt + 1, wait
                )
                await asyncio.sleep(wait)
                last_error = e

        raise LLMError(f"API 调用在 {retry_count + 1} 次尝试后失败") from last_error


# ── OpenAI 兼容客户端 ────────────────────────────────────

class OpenAIClient(BaseLLMClient):
    """OpenAI 兼容 API 客户端（DeepSeek、通义千问、Ollama 等）"""

    async def _call_api(
        self,
        system_prompt: str,
        user_prompt: str,
        on_chunk: Optional[Callable[[str], None]] = None,
    ) -> str:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = await client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                stream=on_chunk is not None,
                timeout=120,
            )
        except Exception as e:
            self._raise_proper_error(e)
            raise  # 不可达，_raise_proper_error 已 raise

        if on_chunk is not None:
            # 流式模式
            full_text: list[str] = []
            async for chunk in response:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    full_text.append(delta.content)
                    on_chunk(delta.content)
            return "".join(full_text)
        else:
            # 非流式模式
            return response.choices[0].message.content or ""

    def _raise_proper_error(self, error: Exception) -> None:
        """将 OpenAI SDK 异常映射到自定义异常"""
        msg = str(error)
        if "429" in msg or "rate limit" in msg.lower():
            raise RateLimitError(msg) from error
        if "401" in msg or "invalid_api_key" in msg.lower() or "unauthorized" in msg.lower():
            raise AuthenticationError(msg) from error
        if "400" in msg or "bad request" in msg.lower():
            raise BadRequestError(msg) from error
        if "timeout" in msg.lower() or "timed out" in msg.lower():
            raise TimeoutError(msg) from error
        raise LLMError(msg) from error


# ── Anthropic 客户端 ─────────────────────────────────────

class AnthropicClient(BaseLLMClient):
    """Anthropic API 客户端（Claude 系列模型）"""

    async def _call_api(
        self,
        system_prompt: str,
        user_prompt: str,
        on_chunk: Optional[Callable[[str], None]] = None,
    ) -> str:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(
            api_key=self.config.api_key,
        )

        messages = [
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = await client.messages.create(
                model=self.config.model,
                system=system_prompt,
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                stream=on_chunk is not None,
            )
        except Exception as e:
            self._raise_proper_error(e)
            raise

        if on_chunk is not None:
            full_text: list[str] = []
            async for event in response:
                if event.type == "content_block_delta" and event.delta.text:
                    full_text.append(event.delta.text)
                    on_chunk(event.delta.text)
            return "".join(full_text)
        else:
            return response.content[0].text if response.content else ""

    def _raise_proper_error(self, error: Exception) -> None:
        msg = str(error)
        if "429" in msg or "rate_limit" in msg:
            raise RateLimitError(msg) from error
        if "401" in msg or "authentication_error" in msg:
            raise AuthenticationError(msg) from error
        if "400" in msg or "invalid_request" in msg:
            raise BadRequestError(msg) from error
        if "timeout" in msg.lower() or "timed out" in msg.lower():
            raise TimeoutError(msg) from error
        raise LLMError(msg) from error


# ── 客户端工厂 ────────────────────────────────────────────

_client_registry: dict[str, type[BaseLLMClient]] = {
    "openai": OpenAIClient,
    "deepseek": OpenAIClient,
    "ollama": OpenAIClient,
    "anthropic": AnthropicClient,
}


def create_client(config: LLMConfig) -> BaseLLMClient:
    """根据配置创建对应的 LLM 客户端实例

    Args:
        config: LLM 配置

    Returns:
        LLM 客户端实例

    Raises:
        ValueError: 不支持的 provider
    """
    provider = config.provider.lower()
    client_cls = _client_registry.get(provider)
    if client_cls is None:
        # 尝试当作 OpenAI 兼容客户端处理
        logger.info("未知 provider '%s'，按 OpenAI 兼容客户端处理", provider)
        _client_registry[provider] = OpenAIClient
        client_cls = OpenAIClient
    return client_cls(config)
