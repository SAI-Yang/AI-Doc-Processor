"""文档处理引擎（核心）

处理流程：
  1. 读取文档 → 2. 智能分段 → 3. 并行调用 LLM → 4. 合并结果 → 5. 写入输出

支持进度回调、错误隔离（单段失败不影响其他段）、可选结果缓存。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .config import AppConfig
from .document import Document, read_document, write_document
from .llm_client import LLMError, create_client, estimate_tokens
from .template_manager import TemplateManager

logger = logging.getLogger(__name__)


# ── 进度回调 ──────────────────────────────────────────────

@dataclass
class ProgressInfo:
    """进度信息"""
    stage: str  # "reading" / "splitting" / "processing" / "merging" / "writing" / "done" / "error"
    current: int = 0
    total: int = 0
    message: str = ""
    error: Optional[str] = None


ProgressCallback = Callable[[ProgressInfo], None]


# ── 分段算法 ──────────────────────────────────────────────

@dataclass
class Chunk:
    """文档片段"""
    index: int
    text: str
    token_count: int
    paragraph_indices: list[int]  # 对应的原始段落索引


def split_into_chunks(
    document: Document,
    max_chunk_tokens: int = 3000,
    overlap_sentences: int = 1,
) -> list[Chunk]:
    """智能分段算法

    策略：
    1. 按段落分割，每段独立
    2. 尝试将小段落合并到前一段，不超过 max_chunk_tokens
    3. 过长的段落按句子边界切割
    4. 在块之间保留少量重叠以避免上下文断裂

    Args:
        document: 文档对象
        max_chunk_tokens: 每块最大 token 数
        overlap_sentences: 块之间重叠的句子数

    Returns:
        分块列表
    """
    if not document.paragraphs:
        # 没有段落结构时，按字符数简单分割
        return _split_by_chars(document.content, max_chunk_tokens)

    # 第一阶段：计算每段的 token 数
    para_tokens = []
    for p in document.paragraphs:
        t = estimate_tokens(p["text"])
        para_tokens.append(t)

    # 第二阶段：合并小段落
    merged = _merge_paragraphs(document.paragraphs, para_tokens, max_chunk_tokens)

    # 第三阶段：按句子拆分超长块
    final_chunks: list[Chunk] = []
    for chunk_idx, (paras, total_tokens) in enumerate(merged):
        if total_tokens <= max_chunk_tokens:
            text = "\n".join(p["text"] for p in paras)
            para_indices = [p["index"] for p in paras]
            final_chunks.append(Chunk(
                index=chunk_idx,
                text=text,
                token_count=total_tokens,
                paragraph_indices=para_indices,
            ))
        else:
            # 超长块：按句子切割
            sub_chunks = _split_long_paragraph(
                paras, max_chunk_tokens, overlap_sentences
            )
            for sc in sub_chunks:
                final_chunks.append(Chunk(
                    index=chunk_idx,
                    text=sc["text"],
                    token_count=sc["tokens"],
                    paragraph_indices=sc["para_indices"],
                ))

    # 重新编号
    for i, chunk in enumerate(final_chunks):
        chunk.index = i

    logger.info(
        "分段完成: %d 段落 → %d 块 (max_tokens=%d)",
        len(document.paragraphs), len(final_chunks), max_chunk_tokens
    )
    return final_chunks


def _merge_paragraphs(
    paragraphs: list[dict],
    para_tokens: list[int],
    max_chunk_tokens: int,
) -> list[tuple[list[dict], int]]:
    """将小段落合并到前一块"""
    merged: list[tuple[list[dict], int]] = []
    current_group: list[dict] = []
    current_tokens = 0

    for para, tokens in zip(paragraphs, para_tokens):
        if tokens > max_chunk_tokens:
            # 超长段落单独成块
            if current_group:
                merged.append((current_group, current_tokens))
                current_group = []
                current_tokens = 0
            merged.append(([para], tokens))
        elif current_tokens + tokens <= max_chunk_tokens:
            current_group.append(para)
            current_tokens += tokens
        else:
            if current_group:
                merged.append((current_group, current_tokens))
            current_group = [para]
            current_tokens = tokens

    if current_group:
        merged.append((current_group, current_tokens))

    return merged


def _split_long_paragraph(
    paragraphs: list[dict],
    max_chunk_tokens: int,
    overlap_sentences: int,
) -> list[dict]:
    """将超长段落按句子边界切割"""
    import re

    text = "\n".join(p["text"] for p in paragraphs)
    para_indices = [p["index"] for p in paragraphs]

    # 按句号、问号、感叹号、换行分割
    sentences = re.split(r"(?<=[。！？.!?\n])\s*", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if len(sentences) <= 1:
        return [{"text": text, "tokens": estimate_tokens(text), "para_indices": para_indices}]

    chunks: list[dict] = []
    start = 0
    while start < len(sentences):
        end = start
        current_tokens = 0
        # 尽可能多地添加句子到当前块
        while end < len(sentences) and current_tokens < max_chunk_tokens:
            end_tokens = estimate_tokens(sentences[end])
            if current_tokens + end_tokens > max_chunk_tokens and current_tokens > 0:
                break
            current_tokens += end_tokens
            end += 1

        chunk_text = "".join(sentences[start:end])
        chunks.append({
            "text": chunk_text,
            "tokens": estimate_tokens(chunk_text),
            "para_indices": para_indices,
        })

        # 重叠移动
        next_start = max(end - overlap_sentences, start + 1)
        if next_start >= end:
            next_start = end
        start = next_start

        # 防止死循环
        if start >= len(sentences):
            break

    return chunks


def _split_by_chars(text: str, max_chunk_tokens: int) -> list[Chunk]:
    """按字符数简单分割（无段落结构时的备选方案）"""
    max_chars = max_chunk_tokens * 2  # 粗略估算
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunk_text = text[start:end]
        chunks.append(Chunk(
            index=len(chunks),
            text=chunk_text,
            token_count=estimate_tokens(chunk_text),
            paragraph_indices=[],
        ))
        start = end

    return chunks


# ── 文档处理引擎 ──────────────────────────────────────────

class ProcessingEngine:
    """文档处理核心引擎

    负责完整的处理流程：读取 → 分段 → LLM 处理 → 合并 → 写入。
    """

    def __init__(
        self,
        config: AppConfig,
        template_manager: Optional[TemplateManager] = None,
        progress_callback: Optional[ProgressCallback] = None,
        use_cache: bool = False,
    ):
        self.config = config
        self.template_manager = template_manager or TemplateManager()
        self.progress_callback = progress_callback
        self.use_cache = use_cache
        self._cache_dir = Path.home() / ".ai-doc-processor" / "cache"

    def _report(self, info: ProgressInfo) -> None:
        """报告进度"""
        if self.progress_callback:
            self.progress_callback(info)
        logger.debug("[%s] %d/%d - %s", info.stage, info.current, info.total, info.message)

    async def process(
        self,
        input_path: Path,
        output_path: Path,
        template_id: str,
        output_format: Optional[str] = None,
    ) -> Path:
        """处理单个文档

        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径（格式由后缀或 output_format 决定）
            template_id: 处理模板 ID
            output_format: 输出格式，None 则从 output_path 后缀推断

        Returns:
            输出文件路径
        """
        # 1. 读取文档
        self._report(ProgressInfo(stage="reading", current=0, total=5,
                                   message=f"读取文档: {input_path.name}"))
        document: Optional[Document] = None
        try:
            document = read_document(input_path)
        except Exception as e:
            self._report(ProgressInfo(stage="error", current=0, total=0,
                                       message=f"读取失败", error=str(e)))
            raise

        self._report(ProgressInfo(stage="reading", current=1, total=5,
                                   message=f"文档: {document.metadata.get('char_count', 0)} 字符, "
                                           f"{document.metadata.get('paragraph_count', 0)} 段落"))

        # 2. 获取模板
        tpl = self.template_manager.get(template_id)
        if tpl is None:
            raise ValueError(f"模板 '{template_id}' 不存在")
        self._report(ProgressInfo(stage="reading", current=2, total=5,
                                   message=f"模板: {tpl.name}"))

        # 3. 智能分段
        self._report(ProgressInfo(stage="splitting", current=0, total=1,
                                   message="正在分段..."))
        max_chunk_tokens = self.config.llm.max_tokens // 2
        chunks = split_into_chunks(document, max_chunk_tokens)
        self._report(ProgressInfo(stage="splitting", current=1, total=1,
                                   message=f"共 {len(chunks)} 段"))

        if not chunks:
            raise ValueError("文档内容为空，无法处理")

        # 4. 创建 LLM 客户端
        llm_client = create_client(self.config.llm)

        # 5. 并行处理各段
        self._report(ProgressInfo(stage="processing", current=0, total=len(chunks),
                                   message="开始处理..."))
        results = await self._process_chunks(llm_client, chunks, template_id)

        # 6. 合并结果
        self._report(ProgressInfo(stage="merging", current=0, total=1,
                                   message="合并处理结果..."))
        merged_paragraphs = self._merge_results(document, chunks, results)
        merged_document = Document(
            path=output_path,
            format=output_format or document.format,
            content="\n".join(p["text"] for p in merged_paragraphs),
            metadata={**document.metadata, "processed": True},
            paragraphs=merged_paragraphs,
        )
        self._report(ProgressInfo(stage="merging", current=1, total=1,
                                   message=f"合并完成: {len(merged_paragraphs)} 段落"))

        # 7. 写入输出
        fmt = output_format or "same_as_input"
        self._report(ProgressInfo(stage="writing", current=0, total=1,
                                   message="写入结果..."))
        output_path = write_document(merged_document, output_path, fmt)
        self._report(ProgressInfo(stage="done", current=1, total=1,
                                   message=f"处理完成: {output_path}"))
        return output_path

    async def _process_chunks(
        self,
        llm_client,
        chunks: list[Chunk],
        template_id: str,
    ) -> list[Optional[str]]:
        """并行处理所有文档块

        Args:
            llm_client: LLM 客户端实例
            chunks: 文档块列表
            template_id: 模板 ID

        Returns:
            处理结果列表，None 表示该段处理失败
        """
        semaphore = asyncio.Semaphore(self.config.processing.max_concurrent)
        results: list[Optional[str]] = [None] * len(chunks)

        async def process_one(chunk: Chunk) -> tuple[int, Optional[str]]:
            async with semaphore:
                # 检查缓存
                if self.use_cache:
                    cached = self._load_cache(template_id, chunk)
                    if cached is not None:
                        logger.debug("缓存命中: chunk %d", chunk.index)
                        return chunk.index, cached

                # 渲染模板
                system_prompt, user_prompt, _temperature, _max_tokens = \
                    self.template_manager.render(template_id, chunk.text)

                self._report(ProgressInfo(
                    stage="processing",
                    current=chunk.index,
                    total=len(chunks),
                    message=f"处理第 {chunk.index + 1}/{len(chunks)} 段 "
                            f"({chunk.token_count} tokens)..."
                ))

                try:
                    result = await llm_client.process_content(
                        content=chunk.text,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        retry_count=self.config.processing.retry_count,
                    )
                    # 写入缓存
                    if self.use_cache:
                        self._save_cache(template_id, chunk, result)
                    return chunk.index, result
                except LLMError as e:
                    logger.error("第 %d 段处理失败: %s", chunk.index, e)
                    self._report(ProgressInfo(
                        stage="error",
                        current=chunk.index,
                        total=len(chunks),
                        message=f"第 {chunk.index + 1} 段处理失败",
                        error=str(e),
                    ))
                    return chunk.index, None

        # 创建所有任务
        tasks = [process_one(chunk) for chunk in chunks]

        # 按完成顺序处理
        for coro in asyncio.as_completed(tasks):
            idx, result = await coro
            results[idx] = result

        return results

    def _merge_results(
        self,
        original: Document,
        chunks: list[Chunk],
        results: list[Optional[str]],
    ) -> list[dict]:
        """将各段处理结果合并回段落结构

        策略：
        - 若某段处理成功，用处理结果替换对应段落
        - 若处理失败，保留原文
        - 合并连续段落到一个段落（保持结构紧凑）

        Args:
            original: 原始文档
            chunks: 分块列表
            results: 各块的处理结果

        Returns:
            合并后的段落列表
        """
        # 建立 chunk -> 段落的映射
        chunk_text_map: dict[int, str] = {}
        for chunk, result in zip(chunks, results):
            if result is not None:
                chunk_text_map[chunk.index] = result

        merged: list[dict] = []
        for chunk in chunks:
            text = chunk_text_map.get(chunk.index) or chunk.text
            merged.append({
                "index": len(merged),
                "text": text,
                "style": "Normal",
            })

        return merged

    # ── 缓存管理 ──────────────────────────────────────

    def _cache_key(self, template_id: str, chunk: Chunk) -> str:
        """生成缓存键"""
        raw = f"{template_id}:{chunk.text}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def _load_cache(self, template_id: str, chunk: Chunk) -> Optional[str]:
        """从缓存加载"""
        if not self.use_cache:
            return None
        key = self._cache_key(template_id, chunk)
        cache_file = self._cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                return data.get("result")
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def _save_cache(self, template_id: str, chunk: Chunk, result: str) -> None:
        """保存到缓存"""
        if not self.use_cache:
            return
        key = self._cache_key(template_id, chunk)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = self._cache_dir / f"{key}.json"
        try:
            cache_file.write_text(
                json.dumps({"result": result}, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as e:
            logger.warning("缓存写入失败: %s", e)

    def clear_cache(self) -> int:
        """清除所有缓存

        Returns:
            清除的文件数
        """
        if not self._cache_dir.exists():
            return 0
        count = 0
        for f in self._cache_dir.glob("*.json"):
            f.unlink()
            count += 1
        logger.info("缓存已清除: %d 个文件", count)
        return count
