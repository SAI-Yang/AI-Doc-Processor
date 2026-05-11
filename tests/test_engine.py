"""文档处理引擎单元测试

测试内容：
- 配置的保存和加载
- 各格式文档读取
- 智能分段算法
- 模板渲染
- 处理流程（mock LLM）
- 流水线配置
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# 配置测试
# ---------------------------------------------------------------------------

class TestConfig(unittest.TestCase):
    """测试配置管理"""

    def setUp(self):
        from app.config import AppConfig, LLMConfig, OutputConfig, ProcessingConfig

        self.config = AppConfig.default()

    def test_default_values(self):
        """默认配置值验证"""
        self.assertEqual(self.config.llm.provider, "deepseek")
        self.assertEqual(self.config.llm.base_url, "https://api.deepseek.com")
        self.assertEqual(self.config.llm.model, "deepseek-chat")
        self.assertEqual(self.config.llm.temperature, 0.3)
        self.assertEqual(self.config.llm.max_tokens, 4096)
        self.assertEqual(self.config.output.format, "same_as_input")
        self.assertEqual(self.config.processing.max_concurrent, 3)
        self.assertEqual(self.config.processing.retry_count, 2)
        self.assertEqual(self.config.processing.timeout, 120)

    def test_validation_empty_api_key(self):
        """空 API 密钥应报告错误"""
        self.config.llm.api_key = ""
        errors = self.config.validate()
        self.assertTrue(any("API 密钥" in e for e in errors))

    def test_validation_invalid_temperature(self):
        """无效 temperature 应报告错误"""
        self.config.llm.api_key = "sk-test"
        self.config.llm.temperature = 3.0
        errors = self.config.validate()
        self.assertTrue(any("temperature" in e for e in errors))

    def test_save_and_load(self, tmp_path: Path = Path("test_config_tmp")):
        """保存和加载配置"""
        import tempfile
        from app.config import AppConfig
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "config.json"
            self.config.llm.api_key = "sk-test-key"
            self.config.llm.model = "gpt-4"
            self.config.processing.max_concurrent = 5

            saved_path = self.config.save(save_path)
            self.assertTrue(saved_path.exists())

            loaded = AppConfig.load(save_path)
            self.assertEqual(loaded.llm.api_key, "sk-test-key")
            self.assertEqual(loaded.llm.model, "gpt-4")
            self.assertEqual(loaded.processing.max_concurrent, 5)

    def test_load_nonexistent_returns_default(self):
        """加载不存在的文件应返回默认配置"""
        from app.config import AppConfig
        config = AppConfig.load(Path("/nonexistent/config.json"))
        self.assertIsInstance(config, AppConfig)


# ---------------------------------------------------------------------------
# 文档读取测试
# ---------------------------------------------------------------------------

class TestDocumentReading(unittest.TestCase):
    """测试各格式文档读取"""

    def setUp(self):
        self.test_dir = Path(__file__).parent / "test_data"
        self.test_dir.mkdir(exist_ok=True)

    def _create_txt(self, content: str) -> Path:
        path = self.test_dir / "test.txt"
        path.write_text(content, encoding="utf-8")
        return path

    def test_txt_reader(self):
        """TXT 读取"""
        from app.document import TxtReader

        txt_path = self._create_txt("第一行\n第二行\n\n第三行")
        reader = TxtReader()
        doc = reader.read(txt_path)

        self.assertEqual(doc.format, "txt")
        self.assertIn("第一行", doc.content)
        self.assertEqual(len(doc.paragraphs), 3)

    def test_md_reader(self):
        """MD 读取"""
        from app.document import MdReader

        md_path = self.test_dir / "test.md"
        md_path.write_text(
            "# 标题\n\n一段落\n\n- 列表项1\n- 列表项2\n\n> 引用",
            encoding="utf-8",
        )
        reader = MdReader()
        doc = reader.read(md_path)

        self.assertEqual(doc.format, "md")
        self.assertEqual(doc.metadata["paragraph_count"], 5)

        # 验证样式检测
        styles = [p["style"] for p in doc.paragraphs]
        self.assertIn("Heading 1", styles)
        self.assertIn("List Item", styles)
        self.assertIn("Blockquote", styles)
        self.assertIn("Normal", styles)

    def test_get_reader_unsupported(self):
        """不支持的格式应抛出 ValueError"""
        from app.document import get_reader

        with self.assertRaises(ValueError):
            get_reader(Path("test.xyz"))

    def test_read_document_integration(self):
        """read_document 集成测试"""
        from app.document import read_document

        txt_path = self._create_txt("Hello World")
        doc = read_document(txt_path)
        self.assertEqual(doc.format, "txt")
        self.assertIn("Hello World", doc.content)

    def tearDown(self):
        # 清理测试文件
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)


# ---------------------------------------------------------------------------
# 分段算法测试
# ---------------------------------------------------------------------------

class TestChunking(unittest.TestCase):
    """测试智能分段算法"""

    def test_empty_paragraphs(self):
        """空文档"""
        from app.engine import split_into_chunks
        from app.document import Document
        from pathlib import Path

        doc = Document(
            path=Path("test.txt"),
            format="txt",
            content="",
            paragraphs=[],
        )
        chunks = split_into_chunks(doc, max_chunk_tokens=100)
        self.assertEqual(len(chunks), 0)

    def test_simple_paragraphs(self):
        """简单分段"""
        from app.engine import split_into_chunks
        from app.document import Document
        from pathlib import Path

        paragraphs = [
            {"index": 0, "text": "短段落", "style": "Normal"},
            {"index": 1, "text": "另一个短段落", "style": "Normal"},
        ]
        doc = Document(
            path=Path("test.txt"),
            format="txt",
            content="短段落\n另一个短段落",
            paragraphs=paragraphs,
        )
        chunks = split_into_chunks(doc, max_chunk_tokens=3000)
        # 两个短段落应合并为一块
        self.assertEqual(len(chunks), 1)

    def test_large_paragraph_split(self):
        """超长段落应按句子分割"""
        from app.engine import split_into_chunks
        from app.document import Document
        from pathlib import Path

        # 构造超过 max_chunk_tokens 的长段落
        long_text = "这是第一句。这是第二句。这是第三句。这是第四句。 " * 20
        paragraphs = [
            {"index": 0, "text": long_text, "style": "Normal"},
        ]
        doc = Document(
            path=Path("test.txt"),
            format="txt",
            content=long_text,
            paragraphs=paragraphs,
        )
        chunks = split_into_chunks(doc, max_chunk_tokens=50)
        # 应该被分割为多块
        self.assertGreater(len(chunks), 1)


# ---------------------------------------------------------------------------
# 模板测试
# ---------------------------------------------------------------------------

class TestTemplateManager(unittest.TestCase):
    """测试模板管理"""

    def setUp(self):
        from app.template_manager import TemplateManager
        self.mgr = TemplateManager()

    def test_list_builtin_templates(self):
        """内置模板数量"""
        templates = self.mgr.list_templates()
        # 9 个内置模板
        builtin = [t for t in templates if t["is_builtin"]]
        self.assertGreaterEqual(len(builtin), 9)

    def test_get_builtin_template(self):
        """获取内置模板"""
        tpl = self.mgr.get("zh_to_en")
        self.assertIsNotNone(tpl)
        self.assertEqual(tpl.name, "中译英")

    def test_get_nonexistent(self):
        """不存在的模板返回 None"""
        tpl = self.mgr.get("nonexistent_template")
        self.assertIsNone(tpl)

    def test_render_template(self):
        """模板渲染"""
        system, user, temp, max_tok = self.mgr.render(
            "zh_to_en",
            "这是一段测试内容"
        )
        self.assertIn("translate", system.lower())
        self.assertIn("这是一段测试内容", user)

    def test_render_nonexistent_raises(self):
        """渲染不存在的模板应抛出 KeyError"""
        with self.assertRaises(KeyError):
            self.mgr.render("nonexistent", "content")

    def test_get_default_template_id(self):
        """默认模板 ID"""
        default_id = self.mgr.get_default_template_id()
        self.assertIsNotNone(default_id)
        self.assertIn(default_id, [
            "zh_to_en", "en_to_zh", "academic_polish",
            "general_polish", "summarize", "key_points",
            "format_normalize", "expand", "simplify",
        ])


# ---------------------------------------------------------------------------
# Token 估算测试
# ---------------------------------------------------------------------------

class TestTokenEstimator(unittest.TestCase):
    """测试 Token 估算"""

    def test_estimate_tokens(self):
        from app.llm_client import estimate_tokens

        # 英文文本
        tokens = estimate_tokens("Hello world")
        self.assertGreater(tokens, 0)

        # 中文文本
        tokens_cn = estimate_tokens("这是一段中文文本")
        self.assertGreater(tokens_cn, 0)

        # 空文本
        tokens_empty = estimate_tokens("")
        self.assertEqual(tokens_empty, 1)  # 至少 1


# ---------------------------------------------------------------------------
# Mock 处理引擎测试
# ---------------------------------------------------------------------------

class TestProcessingEngine(unittest.TestCase):
    """测试处理引擎（mock LLM）"""

    def setUp(self):
        from app.config import AppConfig
        from app.engine import ProcessingEngine
        from app.template_manager import TemplateManager

        self.config = AppConfig.default()
        self.config.llm.api_key = "sk-mock-key"
        self.template_mgr = TemplateManager()
        self.engine = ProcessingEngine(
            config=self.config,
            template_manager=self.template_mgr,
        )

    @patch("app.llm_client.OpenAIClient.process_content", new_callable=AsyncMock)
    def test_process_simple_txt(self, mock_process):
        """测试处理简单 TXT 文件"""
        import asyncio
        import tempfile
        from pathlib import Path

        mock_process.return_value = "模拟处理结果"

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.txt"
            input_path.write_text("这是一段测试文本", encoding="utf-8")
            output_path = Path(tmpdir) / "output.txt"

            result = asyncio.run(
                self.engine.process(
                    input_path=input_path,
                    output_path=output_path,
                    template_id="zh_to_en",
                )
            )

            self.assertTrue(result.exists())
            self.assertGreater(result.stat().st_size, 0)

    def test_process_no_api_key(self):
        """未设置 API 密钥时应报告错误"""
        self.config.llm.api_key = ""
        errors = self.config.validate()
        self.assertTrue(any("API 密钥" in e for e in errors))


# ---------------------------------------------------------------------------
# 流水线测试
# ---------------------------------------------------------------------------

class TestPipeline(unittest.TestCase):
    """测试流水线配置"""

    def test_pipeline_config_serialization(self):
        """流水线配置序列化/反序列化"""
        from app.pipeline import PipelineConfig, PipelineStep

        config = PipelineConfig(
            name="测试流水线",
            steps=[
                PipelineStep(template_id="en_to_zh", description="翻译"),
                PipelineStep(template_id="academic_polish", description="润色"),
            ],
        )

        d = {
            "name": "测试流水线",
            "steps": [
                {"template_id": "en_to_zh", "description": "翻译", "output_format": None},
                {"template_id": "academic_polish", "description": "润色", "output_format": None},
            ],
            "output_dir": None,
        }

        from app.pipeline import Pipeline

        # 模拟 pipeline 的 to_dict
        pipeline = Pipeline.__new__(Pipeline)
        pipeline.pipeline_config = config
        exported = pipeline.to_dict()

        self.assertEqual(exported["name"], "测试流水线")
        self.assertEqual(len(exported["steps"]), 2)

    def test_create_default_pipelines(self):
        """预设流水线"""
        from app.pipeline import create_default_pipelines

        pipelines = create_default_pipelines()
        self.assertGreater(len(pipelines), 0)

    def test_empty_pipeline_raises(self):
        """空流水线应抛出错误"""
        from app.pipeline import Pipeline, PipelineConfig
        from app.config import AppConfig

        config = AppConfig.default()
        pipeline = Pipeline(config, PipelineConfig(name="空流水线"))

        # 不能用 pytest.raises 因为 run 是 async
        import asyncio
        with self.assertRaises(ValueError):
            asyncio.run(pipeline.run(Path("in.txt"), Path("out.txt")))


# ---------------------------------------------------------------------------
# LLM 客户端测试
# ---------------------------------------------------------------------------

class TestLLMClient(unittest.TestCase):
    """测试 LLM 客户端"""

    def test_create_openai_client(self):
        """创建 OpenAI 客户端"""
        from app.llm_client import create_client
        from app.config import LLMConfig

        config = LLMConfig(provider="openai", api_key="sk-test")
        client = create_client(config)
        from app.llm_client import OpenAIClient
        self.assertIsInstance(client, OpenAIClient)

    def test_create_anthropic_client(self):
        """创建 Anthropic 客户端"""
        from app.llm_client import create_client
        from app.config import LLMConfig

        config = LLMConfig(provider="anthropic", api_key="sk-test")
        client = create_client(config)
        from app.llm_client import AnthropicClient
        self.assertIsInstance(client, AnthropicClient)

    def test_create_unknown_provider_fallback(self):
        """未知 provider 应回退到 OpenAI 兼容"""
        from app.llm_client import create_client, OpenAIClient
        from app.config import LLMConfig

        config = LLMConfig(provider="unknown_provider", api_key="sk-test")
        client = create_client(config)
        self.assertIsInstance(client, OpenAIClient)

    def test_estimate_tokens(self):
        """Token 估算"""
        from app.llm_client import estimate_tokens

        # 纯英文
        en_tokens = estimate_tokens("Hello, this is a test message for token estimation.")
        self.assertGreaterEqual(en_tokens, 1)

        # 纯中文
        cn_tokens = estimate_tokens("这是一段用于测试 Token 估算的中文文本。")
        self.assertGreaterEqual(cn_tokens, 1)

        # 混合
        mix_tokens = estimate_tokens("混合 English 和 中文 text")
        self.assertGreaterEqual(mix_tokens, 1)


# ---------------------------------------------------------------------------
# 文档写入测试
# ---------------------------------------------------------------------------

class TestDocumentWriting(unittest.TestCase):
    """测试文档写入"""

    def test_txt_writer(self):
        """TXT 写入"""
        import tempfile
        from app.document import Document, TxtWriter
        from pathlib import Path

        doc = Document(
            path=Path("input.txt"),
            format="txt",
            content="Hello\nWorld",
            paragraphs=[
                {"index": 0, "text": "Hello", "style": "Normal"},
                {"index": 1, "text": "World", "style": "Normal"},
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "output.txt"
            writer = TxtWriter()
            result = writer.write(doc, output)
            self.assertTrue(result.exists())
            content = result.read_text(encoding="utf-8")
            self.assertIn("Hello", content)
            self.assertIn("World", content)


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
