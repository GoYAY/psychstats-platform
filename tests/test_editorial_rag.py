import importlib.util
import pathlib
import sys
import unittest
import pickle
import tempfile

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'rag'))


class EditorialRagTests(unittest.TestCase):
    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('editorial_rag'), 'candidate module is required')
        import editorial_rag
        return editorial_rag

    def test_formula_routes_to_citable_external_evidence(self):
        m = self.api()
        result = m.route_field('formula')
        self.assertEqual(result['channel'], 'external_verified')
        self.assertFalse(result['allow_ocr_formula'])
        self.assertEqual(m.route_field('definition')['channel'], 'textbook_rag')
        with self.assertRaises(ValueError):
            m.route_field('made_up_field')

    def test_sentence_chunks_honor_target_and_keep_citation(self):
        m = self.api()
        page = {'id': 'basic:page:7', 'source': 'basic', 'doc': 'basic', 'page_pdf': 7,
                'text': ('这是一个完整定义，包含必要条件。' * 12), 'method': 'PDF_TEXT_LAYER'}
        small = m.chunk_page(page, target=45, maxlen=70, overlap=0)
        large = m.chunk_page(page, target=150, maxlen=180, overlap=0)
        self.assertGreater(len(small), len(large))
        self.assertTrue(all(len(x['text']) <= 70 for x in small))
        self.assertTrue(all(x['parent_id'] == page['id'] and x['page_pdf'] == 7 for x in small))
        self.assertTrue(all(x['text'].endswith('。') for x in small))

    def test_single_long_line_is_bounded_without_character_loss(self):
        m = self.api()
        page = {'id': 'p', 'source': 'course', 'doc': 'x', 'page_pdf': 1,
                'text': 'abcdefghijklmn' * 50, 'method': 'PDF_TEXT_LAYER'}
        chunks = m.chunk_page(page, target=100, maxlen=140, overlap=0)
        self.assertEqual(''.join(c['text'] for c in chunks), page['text'])
        self.assertLessEqual(max(len(c['text']) for c in chunks), 140)

    def test_english_definition_not_rejected_for_low_chinese_ratio(self):
        m = self.api()
        self.assertEqual(m.content_status('A residual is the observed response minus the fitted response.')['status'], 'usable')
        self.assertNotEqual(m.content_status('1 2 3 4 0.01 0.23 0.50')['status'], 'usable')

    def test_known_false_inference_is_quarantined(self):
        m = self.api()
        bad = '若没有不合理现象出现，那就认为“虚无假设为真”的假定是正确的，也就是说要接受虚无假设。'
        self.assertEqual(m.content_status(bad)['status'], 'quarantined')
        self.assertEqual(m.content_status('p 接受H0，拒绝H1，否则接受H1')['status'], 'quarantined')
        self.assertEqual(m.content_status('未拒绝零假设不等于证明零假设为真。')['status'], 'usable')

    def test_parent_expansion_stays_in_document_and_budget(self):
        m = self.api()
        pages = {'a': {'id': 'a', 'doc': 'A', 'source': 'course', 'page_pdf': 3, 'text': '甲' * 600},
                 'b': {'id': 'b', 'doc': 'B', 'source': 'course', 'page_pdf': 3, 'text': '乙' * 600}}
        rows = [{'parent_id': 'a', 'source': 'course', 'doc': 'A', 'text': '甲' * 80}]
        expanded = m.expand_context(rows, pages, budget=300)
        self.assertLessEqual(sum(len(x['text']) for x in expanded), 300)
        self.assertTrue(all(x['doc'] == 'A' for x in expanded))
        self.assertTrue(all('乙' not in x['text'] for x in expanded))

    def test_parent_expansion_deduplicates_same_page(self):
        m = self.api()
        pages = {'a': {'id': 'a', 'doc': 'A', 'source': 'course', 'page_pdf': 3, 'text': '同页正文' * 20}}
        rows = [{'parent_id': 'a', 'source': 'course', 'doc': 'A', 'text': '正文'}] * 3
        self.assertEqual(len(m.expand_context(rows, pages, budget=300)), 1)

    def test_tiny_remaining_budget_does_not_emit_prose_fragment(self):
        m = self.api()
        page = {'id': 'p', 'doc': 'A', 'source': 'course', 'page_pdf': 3,
                'text': '首先需要区分总体均值和样本均值，并标出测量单位。'}
        child = dict(page, parent_id='p')
        self.assertEqual(m.expand_context([child], {'p': page}, budget=2), [])
        self.assertEqual(m.evidence_context([page], [], {'p': page}, budget=2), [])

    def test_context_never_returns_known_bad_parent_unmarked(self):
        m = self.api()
        bad = 'p 接受H0，拒绝H1，否则接受H1'
        pages = {'a': {'id': 'a', 'doc': 'A', 'source': 'course', 'page_pdf': 3, 'text': '定义是比较观察结果。' + bad}}
        rows = [{'parent_id': 'a', 'source': 'course', 'doc': 'A', 'text': '定义是比较观察结果。'}]
        expanded = m.expand_context(rows, pages, budget=300)
        self.assertTrue(all(bad not in x['text'] for x in expanded))

    def test_child_semantics_choose_explanation_over_same_page_heading(self):
        m = self.api()
        page = {'id': 'p', 'source': 'course', 'doc': 'x', 'page_pdf': 1, 'text': '完整页'}
        rows = [dict(page, id='a', parent_id='p', text='本章节内容：p值定义、p值原理、p值应用。', quality={'status': 'usable'}),
                dict(page, id='b', parent_id='p', text='零假设下，p值表示获得至少同等极端结果的概率。', quality={'status': 'usable'})]
        data = {'pages': {'p': page}, 'chunks': rows, 'legacy_embeddings': np.array([[1., 0.]]),
                'child_embeddings': np.array([[0., 1.], [1., 0.]]), 'parent_legacy': {'p': [0]}}
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / 'index.pkl'
            with path.open('wb') as f:
                pickle.dump(data, f)
            retriever = m.EditorialRetriever(path)
            result = retriever.retrieve('p值', k=1, query_vectors=np.array([[1., 0.]] * 3), include_anchors=False)
            self.assertEqual(result['rows'][0]['id'], 'b')

    def test_reviewed_bad_span_cannot_escape_across_child_boundary(self):
        m = self.api()
        self.assertTrue(hasattr(m, 'reviewed_status'), 'reviewed interval isolation is required')
        parent = {'id': 'p', 'source': 'basic', 'doc': 'basic', 'page_pdf': 3,
                  'text': '这是一个完整而且可用的概念定义。错误推断第一句，错误推断第二句。随后是其他说明。'}
        rule = {'source': 'basic', 'doc': 'basic', 'page_pdf': 3,
                'match_text': '错误推断第一句，错误推断第二句。', 'id': 'r1'}
        child = dict(parent, parent_id='p', text='错误推断第二句。随后是其他说明。')
        self.assertEqual(m.reviewed_status(child, {'p': parent}, [rule])['status'], 'quarantined')
        safe = dict(parent, parent_id='p', text='这是一个完整而且可用的概念定义。')
        self.assertEqual(m.reviewed_status(safe, {'p': parent}, [rule])['status'], 'usable')

    def test_public_anchor_response_excludes_quarantined_raw_text(self):
        m = self.api()
        self.assertTrue(hasattr(m, 'safe_anchors'), 'public anchors must be sanitized')
        raw = [{'source': 'course', 'doc': 'x', 'page_pdf': 1, 'chunk_id': 7,
                'text': 'p 接受H0，拒绝H1，否则接受H1'}]
        safe, audit = m.safe_anchors(raw, {})
        self.assertEqual(safe, [])
        self.assertEqual(audit[0]['chunk_id'], 7)
        self.assertNotIn('text', audit[0])

    def test_model_payload_does_not_duplicate_diagnostic_passages(self):
        m = self.api()
        self.assertTrue(hasattr(m, 'model_payload'), 'model-facing projection is required')
        result = {'channel': 'textbook_rag', 'term': {'slug': 'x'}, 'field': 'definition',
                  'rows': [{'text': '诊断子块'}], 'anchor_rows': [{'text': '诊断锚点'}],
                  'contexts': [{'text': '实际交付正文', 'source': 'basic', 'page_pdf': 3}],
                  'context_characters': 6, 'context_budget': 100}
        payload = m.model_payload(result)
        self.assertNotIn('rows', payload)
        self.assertNotIn('anchor_rows', payload)
        self.assertEqual(payload['contexts'][0]['text'], '实际交付正文')

    def test_primary_ranking_preserves_coarse_order_and_fills_without_duplicates(self):
        m = self.api()
        self.assertTrue(hasattr(m, 'primary_ranking'), 'coarse primary ranking contract is required')
        anchors = [{'id': 'a', 'text': '第一条完整证据'}, {'id': 'b', 'text': '第二条完整证据'}]
        fine = [{'id': 'duplicate', 'text': '第一条完整证据'}, {'id': 'c', 'text': '补充证据'}]
        result = m.primary_ranking(anchors, fine, k=3)
        self.assertEqual([r['id'] for r in result], ['a', 'b', 'c'])
        self.assertEqual([r['rank'] for r in result], [1, 2, 3])


if __name__ == '__main__':
    unittest.main()
