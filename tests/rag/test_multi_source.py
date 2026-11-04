import unittest
from unittest.mock import patch

import numpy as np

from rag import rag_multi


def store(text):
    return {
        "chunks": [{"chunk_id": 0, "text": text, "source": "fixture"}],
        "emb": np.asarray([[1.0, 0.0]], dtype=np.float32),
        "bm25": rag_multi.BM25([rag_multi.tokenize(text)]),
        "meta": {},
    }


class MultiSourceTests(unittest.TestCase):
    def test_legacy_default_still_queries_textbook_and_course(self):
        with patch.object(rag_multi, "load_textbook", return_value=store("高级模型")), patch.object(
            rag_multi, "load_course", return_value=store("课程解释")
        ), patch.object(rag_multi, "embed_texts", return_value=np.asarray([[1.0, 0.0]])):
            rows = rag_multi.retrieve_multi("模型", k=2, min_pool=1)
        self.assertEqual({row["source"] for row in rows}, {"textbook", "course"})

    def test_basic_source_can_be_selected_exclusively(self):
        with patch.object(rag_multi, "load_basic", return_value=store("平均数与标准差")), patch.object(
            rag_multi, "embed_texts", return_value=np.asarray([[1.0, 0.0]])
        ):
            rows = rag_multi.retrieve_multi("平均数", k=1, sources={"basic"}, min_pool=1)
        self.assertEqual([row["source"] for row in rows], ["basic"])

    def test_unknown_source_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown source"):
            rag_multi.retrieve_multi("均值", sources={"internet"})


if __name__ == "__main__":
    unittest.main()
