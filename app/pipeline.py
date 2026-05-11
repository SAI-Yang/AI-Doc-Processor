"""多步骤处理流水线

支持串联多个处理步骤（如：先翻译 → 再润色 → 再摘要）。
中间结果自动保存，支持流水线配置导入/导出。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable, Optional

from .config import AppConfig
from .engine import ProcessingEngine, ProgressInfo

logger = logging.getLogger(__name__)


@dataclass
class PipelineStep:
    """流水线步骤定义"""
    template_id: str  # 处理模板 ID
    description: str = ""  # 步骤描述
    output_format: Optional[str] = None  # 本步骤输出格式


@dataclass
class PipelineConfig:
    """流水线配置"""
    name: str = "未命名流水线"
    description: str = ""  # 流水线说明
    steps: list[PipelineStep] = field(default_factory=list)
    output_dir: Optional[str] = None  # 中间结果输出目录


class Pipeline:
    """多步骤处理流水线

    按顺序执行多个处理步骤，前一步的输出是后一步的输入。
    每步之间可保存中间结果。
    """

    def __init__(
        self,
        config: AppConfig,
        pipeline_config: PipelineConfig,
        progress_callback: Optional[Callable[[ProgressInfo], None]] = None,
    ):
        self.config = config
        self.pipeline_config = pipeline_config
        self.progress_callback = progress_callback

    async def run(
        self,
        input_path: Path,
        output_path: Path,
    ) -> Path:
        """运行完整流水线

        Args:
            input_path: 输入文件路径
            output_path: 最终输出路径

        Returns:
            最终输出文件路径
        """
        if not self.pipeline_config.steps:
            raise ValueError("流水线中没有定义处理步骤")

        current_input = input_path
        total_steps = len(self.pipeline_config.steps)

        for step_idx, step in enumerate(self.pipeline_config.steps):
            step_num = step_idx + 1
            desc = step.description or step.template_id

            # 确定本步骤输出路径
            is_last = (step_idx == total_steps - 1)
            if is_last:
                step_output = output_path
            else:
                step_output = self._get_intermediate_path(
                    input_path, step_idx, step.template_id
                )

            logger.info("流水线步骤 %d/%d: %s -> %s", step_num, total_steps, desc, step_output)

            # 上报步骤进度
            if self.progress_callback:
                self.progress_callback(ProgressInfo(
                    stage=f"pipeline_step_{step_num}",
                    current=step_idx,
                    total=total_steps,
                    message=f"步骤 {step_num}/{total_steps}: {desc}",
                ))

            # 创建步骤级进度回调
            def make_step_callback(s_idx: int, s_total: int, s_desc: str):
                def cb(info: ProgressInfo) -> None:
                    if self.progress_callback:
                        self.progress_callback(ProgressInfo(
                            stage=f"pipeline_step_{s_idx + 1}",
                            current=s_idx,
                            total=s_total,
                            message=f"[{s_desc}] {info.message}",
                            error=info.error,
                        ))
                return cb

            # 执行本步骤
            engine = ProcessingEngine(
                config=self.config,
                progress_callback=make_step_callback(step_idx, total_steps, desc),
            )

            result_path = await engine.process(
                input_path=current_input,
                output_path=step_output,
                template_id=step.template_id,
                output_format=step.output_format,
            )

            # 下一步的输入 = 本步骤的输出
            current_input = result_path

        if self.progress_callback:
            self.progress_callback(ProgressInfo(
                stage="pipeline_done",
                current=total_steps,
                total=total_steps,
                message=f"流水线完成: {output_path}",
            ))

        return output_path

    def _get_intermediate_path(
        self, input_path: Path, step_idx: int, template_id: str
    ) -> Path:
        """生成中间结果路径"""
        output_dir = Path(self.pipeline_config.output_dir or input_path.parent)
        output_dir.mkdir(parents=True, exist_ok=True)
        stem = input_path.stem
        return output_dir / f"{stem}_step{step_idx + 1}_{template_id}.txt"

    # ── 配置序列化 ──────────────────────────────────────

    def to_dict(self) -> dict:
        """导出流水线配置为字典"""
        return {
            "name": self.pipeline_config.name,
            "description": self.pipeline_config.description,
            "steps": [
                {
                    "template_id": s.template_id,
                    "description": s.description,
                    "output_format": s.output_format,
                }
                for s in self.pipeline_config.steps
            ],
            "output_dir": self.pipeline_config.output_dir,
        }

    def save_config(self, path: Path) -> None:
        """保存流水线配置到 JSON 文件"""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("流水线配置已保存到 %s", path)

    @classmethod
    def load_config(cls, path: Path) -> PipelineConfig:
        """从 JSON 文件加载流水线配置

        Args:
            path: 配置文件路径

        Returns:
            PipelineConfig 实例
        """
        data = json.loads(path.read_text(encoding="utf-8"))
        steps = [
            PipelineStep(
                template_id=s["template_id"],
                description=s.get("description", ""),
                output_format=s.get("output_format"),
            )
            for s in data.get("steps", [])
        ]
        return PipelineConfig(
            name=data.get("name", "导入的流水线"),
            description=data.get("description", ""),
            steps=steps,
            output_dir=data.get("output_dir"),
        )


# ── 预设流水线 ────────────────────────────────────────────

def create_default_pipelines() -> list[PipelineConfig]:
    """创建预设流水线配置列表"""
    return [
        PipelineConfig(
            name="翻译+润色",
            description="先翻译成中文，再进行学术润色",
            steps=[
                PipelineStep(
                    template_id="en_to_zh",
                    description="英译中",
                ),
                PipelineStep(
                    template_id="academic_polish",
                    description="学术润色",
                ),
            ],
        ),
        PipelineConfig(
            name="摘要+要点",
            description="先生成摘要，再提取关键点",
            steps=[
                PipelineStep(
                    template_id="summarize",
                    description="生成摘要",
                    output_format="txt",
                ),
                PipelineStep(
                    template_id="key_points",
                    description="提取要点",
                ),
            ],
        ),
        PipelineConfig(
            name="格式规范化+简化",
            description="先规范格式，再简化为易懂版本",
            steps=[
                PipelineStep(
                    template_id="format_normalize",
                    description="格式规范化",
                ),
                PipelineStep(
                    template_id="simplify",
                    description="简化文本",
                ),
            ],
        ),
    ]
