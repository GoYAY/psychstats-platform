import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'rag'))


class EditorialRerankTests(unittest.TestCase):
    def test_definition_from_short_pool_can_outrank_legacy_noise(self):
        from editorial_rerank import rank_evidence
        bibliography = {'id': 'legacy:textbook:1', 'source': 'textbook', 'doc': 'advanced',
                        'page_pdf': 430, 'text': '参考文献\nA. Author (2024). Odds ratios in regression.'}
        definition = {'id': 'child:1', 'source': 'course', 'doc': 'logistic', 'page_pdf': 5,
                      'text': '优势比是两个发生比的比值，常用于解释 Logistic 回归系数。'}
        rows = rank_evidence([bibliography, definition], [0.80, 0.75], ['优势比', 'odds ratio'], 2)
        self.assertEqual(rows[0]['id'], 'child:1')

    def test_relation_query_uses_one_valid_edge_and_rejects_curriculum_next(self):
        from editorial_rerank import related_query
        catalog = {'measurement-model': {'zh': '测量模型'}, 'cfa': {'zh': '验证性因素分析'},
                   'structural-model': {'zh': '结构模型'}}
        with tempfile.TemporaryDirectory() as directory:
            folder = pathlib.Path(directory)
            (folder / 'measurement-model.json').write_text(
                '{"relations":{"used_in":["unavailable","cfa"],"contrasts":["structural-model"],'
                '"next":["measurement-model"]}}', encoding='utf-8')
            self.assertEqual(related_query('measurement-model', 'definition', catalog, folder)['slug'], 'cfa')
            self.assertEqual(related_query('measurement-model', 'pitfalls', catalog, folder)['slug'], 'structural-model')
            self.assertIsNone(related_query('../measurement-model', 'definition', catalog, folder))
            (folder / 'measurement-model.json').write_text('{"relations":{"next":["cfa"]}}', encoding='utf-8')
            self.assertIsNone(related_query('measurement-model', 'definition', catalog, folder))
