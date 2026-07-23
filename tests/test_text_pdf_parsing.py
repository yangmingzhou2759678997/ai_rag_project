import unittest
from pathlib import Path

from pypdf import PdfReader

# 复用现有测试的轻量导入替换，避免加载配置、数据库和外部模型客户端
from tests.test_docx_section_chunking import extract_file_text, split_text


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "rag_eval"


def read_fixture(file_name):
    return (FIXTURE_DIR / file_name).read_bytes()


class TestTextPdfParsing(unittest.TestCase):
    def test_txt_contains_body_and_final_paragraph(self):
        """验证TXT普通正文和最后一段都能提取"""
        text = extract_file_text("rag_eval_basic.txt", read_fixture("rag_eval_basic.txt"))
        self.assertIn("紫色工单必须由客服主管和合规专员完成双签", text)
        self.assertIn("TXT-FINAL-731", text)

    def test_txt_long_paragraph_is_split(self):
        """验证TXT长段落能够切成多个Chunk"""
        text = extract_file_text("rag_eval_basic.txt", read_fixture("rag_eval_basic.txt"))
        chunks = split_text(text, 350, 50)
        self.assertGreater(len(chunks), 1)
        self.assertIn("这段说明故意超过默认chunk_size", "".join(chunks))

    def test_markdown_contains_heading_and_lists(self):
        """验证Markdown标题和两种列表文字都能提取"""
        text = extract_file_text("rag_eval_technical.md", read_fixture("rag_eval_technical.md"))
        self.assertIn("# 云帆发布操作手册", text)
        self.assertIn("1. 核对版本编号", text)
        self.assertIn("- 确认数据库备份已经完成", text)

    def test_markdown_contains_code_and_config(self):
        """验证Markdown代码块中的命令和配置值都能提取"""
        text = extract_file_text("rag_eval_technical.md", read_fixture("rag_eval_technical.md"))
        self.assertIn("python -m uvicorn main:app --host 127.0.0.1 --port 8123", text)
        self.assertIn("RETRY_LIMIT=4", text)

    def test_markdown_contains_final_line(self):
        """验证Markdown最后一行验收标记不会丢失"""
        text = extract_file_text("rag_eval_technical.md", read_fixture("rag_eval_technical.md"))
        self.assertTrue(text.strip().endswith("MD-FINAL-842"))

    def test_pdf_contains_all_text_pages(self):
        """验证PDF共有四页且第1、2、4页包含文字"""
        pdf_reader = PdfReader(FIXTURE_DIR / "rag_eval_pages.pdf")
        page_texts = [(page.extract_text() or "").strip() for page in pdf_reader.pages]
        self.assertEqual(len(page_texts), 4)
        self.assertTrue(page_texts[0] and page_texts[1] and page_texts[3])
        self.assertEqual(page_texts[2], "")

    def test_pdf_contains_cross_page_evidence(self):
        """验证PDF跨页关联事实的两部分都能提取"""
        text = extract_file_text("rag_eval_pages.pdf", read_fixture("rag_eval_pages.pdf"))
        self.assertIn("主节点编号为DB-A17", text)
        self.assertIn("备用节点编号为DB-B29", text)
        self.assertIn("DR_MODE=warm", text)

    def test_pdf_contains_last_page_marker(self):
        """验证PDF最后一页正文和验收标记都能提取"""
        text = extract_file_text("rag_eval_pages.pdf", read_fixture("rag_eval_pages.pdf"))
        self.assertIn("最终演练报告存放在E-77柜并保留210天", text)
        self.assertIn("PDF-FINAL-175", text)

    def test_all_fixtures_generate_chunks(self):
        """验证五份非空资料都至少生成一个Chunk"""
        file_names = ["rag_eval_basic.txt", "rag_eval_technical.md", "rag_eval_normal.docx", "rag_eval_table.docx", "rag_eval_pages.pdf"]

        for file_name in file_names:
            text = extract_file_text(file_name, read_fixture(file_name))
            self.assertTrue(split_text(text, 350, 50), file_name)

    def test_non_docx_formats_use_normal_split(self):
        """验证TXT、Markdown和PDF仍能走普通提取与切分流程"""
        for file_name in ["rag_eval_basic.txt", "rag_eval_technical.md", "rag_eval_pages.pdf"]:
            text = extract_file_text(file_name, read_fixture(file_name))
            self.assertTrue(text.strip(), file_name)
            self.assertTrue(split_text(text, 350, 50), file_name)


if __name__ == "__main__":
    unittest.main()
