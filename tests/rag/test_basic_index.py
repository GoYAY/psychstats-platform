import unittest
import pickle
from pathlib import Path

from rag.build_index_basic import DEFAULT_PDF, inspect_pdf, make_chunks


PDF = DEFAULT_PDF
INDEX = Path(__file__).resolve().parents[2] / "rag" / "rag_data" / "index_basic.pkl"


class BasicIndexTests(unittest.TestCase):
    def test_pdf_has_466_pages_and_nearly_complete_text_layer(self):
        inspection = inspect_pdf(PDF)
        self.assertEqual(inspection.page_count, 466)
        self.assertGreaterEqual(inspection.nonempty_pages, 450)
        self.assertEqual(len(inspection.src_sha256), 64)
        self.assertEqual(inspection.extraction_method, "text-layer")

    def test_chunks_have_source_chapter_page_and_fingerprint_metadata(self):
        pages = [
            "1\n第一章 绪论\n心理与教育统计学用于整理和解释数据。",
            "2\n第一节 变量\n变量可以有不同测量尺度。",
        ]
        chunks = make_chunks(pages, src_sha256="a" * 64, target=20)
        self.assertTrue(chunks)
        required = {"source", "chapter", "page_pdf", "page_print", "src_sha256", "text"}
        self.assertTrue(required.issubset(chunks[0]))
        self.assertEqual(chunks[0]["source"], "basic")
        self.assertEqual(chunks[0]["chapter"], "第一章 绪论")

    def test_built_index_is_separate_fresh_and_text_layer_only(self):
        with INDEX.open("rb") as handle:
            payload = pickle.load(handle)
        self.assertEqual(payload["source"], "basic")
        self.assertEqual(payload["page_count"], 466)
        self.assertEqual(payload["extraction_method"], "text-layer")
        self.assertEqual(payload["src_sha256"], payload["chunks"][0]["src_sha256"])
        self.assertGreater(len(payload["chunks"]), 500)


if __name__ == "__main__":
    unittest.main()
