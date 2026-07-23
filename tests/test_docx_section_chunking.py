import sys
import types
import unittest
from io import BytesIO

from docx import Document as WordDocument


# 只测试DOCX文本处理，避免加载真实配置、数据库和外部接口
config_module = types.ModuleType("config")
config_module.settings = types.SimpleNamespace()
models_module = types.ModuleType("models")
models_module.Document = object
sqlalchemy_module = types.ModuleType("sqlalchemy")
sqlalchemy_module.select = None
sqlalchemy_ext_module = types.ModuleType("sqlalchemy.ext")
sqlalchemy_asyncio_module = types.ModuleType("sqlalchemy.ext.asyncio")
sqlalchemy_asyncio_module.AsyncSession = object
rag_tool_module = types.ModuleType("tools.rag_tool")
rag_tool_module.get_text_embedding = None
logger_module = types.ModuleType("utils.logger")
logger_module.logger = types.SimpleNamespace(info=lambda *args, **kwargs: None, error=lambda *args, **kwargs: None)
sys.modules["config"] = config_module
sys.modules["models"] = models_module
sys.modules["sqlalchemy"] = sqlalchemy_module
sys.modules["sqlalchemy.ext"] = sqlalchemy_ext_module
sys.modules["sqlalchemy.ext.asyncio"] = sqlalchemy_asyncio_module
sys.modules["tools.rag_tool"] = rag_tool_module
sys.modules["utils.logger"] = logger_module

from services.knowledge_service import extract_file_text, get_docx_table_text, iter_docx_blocks, split_docx_by_sections
from utils.text_splitter import split_text


def document_to_bytes(document):
    file_buffer = BytesIO()
    document.save(file_buffer)
    return file_buffer.getvalue()


def create_docx(paragraphs):
    document = WordDocument()

    for text in paragraphs:
        document.add_paragraph(text)

    return document_to_bytes(document)


class TestDocxSectionChunking(unittest.TestCase):
    def test_day_five_inherits_stage_and_section(self):
        file_content = create_docx(["第一阶段：基础", "第5天：函数", "默认参数", "*args", "第6天：推导式", "列表推导式"])
        chunks = split_docx_by_sections(file_content, 350, 50)
        day_five_chunks = [item for item in chunks if "第5天" in item["section_title"]]
        self.assertTrue(day_five_chunks)

        for item in day_five_chunks:
            self.assertIn("第一阶段", item["stage_title"])
            self.assertIn("第5天", item["section_title"])
            self.assertNotIn("列表推导式", item["content"])

    def test_same_day_in_two_stages(self):
        file_content = create_docx(["第一阶段：基础", "第5天：函数", "第一阶段正文", "第二阶段：后端", "第五天：接口", "第二阶段正文"])
        chunks = split_docx_by_sections(file_content, 350, 50)
        day_chunks = [item for item in chunks if "天" in item["section_title"]]
        self.assertEqual(len(day_chunks), 2)
        self.assertIn("第一阶段正文", day_chunks[0]["content"])
        self.assertNotIn("第二阶段正文", day_chunks[0]["content"])
        self.assertIn("第二阶段正文", day_chunks[1]["content"])
        self.assertNotIn("第一阶段正文", day_chunks[1]["content"])

    def test_day_chapter_and_section_titles(self):
        file_content = create_docx(["第三阶段：进阶", "第十二天：工具", "第十二天正文", "第一章：基础", "第一章正文", "第2节：练习", "第2节正文"])
        chunks = split_docx_by_sections(file_content, 350, 50)
        section_titles = [item["section_title"] for item in chunks]
        self.assertEqual(section_titles, ["第十二天：工具", "第一章：基础", "第2节：练习"])

    def test_plain_docx_falls_back(self):
        file_content = create_docx(["普通第一段", "普通第二段"])
        self.assertIsNone(split_docx_by_sections(file_content, 350, 50))
        raw_text = extract_file_text("plain.docx", file_content)
        self.assertEqual(split_text(raw_text, 350, 50), ["普通第一段\n普通第二段"])


if __name__ == "__main__":
    unittest.main()
