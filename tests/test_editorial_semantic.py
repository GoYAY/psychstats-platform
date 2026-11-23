import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'rag'))

from editorial_semantic import assess, pack_verified, select


def row(ident, page, text):
    return {'id': str(ident), 'source': 'textbook', 'doc': 'advanced', 'page_pdf': page, 'text': text}


class EditorialSemanticTests(unittest.TestCase):
    def test_rejects_a_quote_that_cannot_be_located(self):
        rows = [row(1, 1, '不同观测之间需要相互独立。'), row(2, 2, '在这里只需要比较两组结果。')]
        answer = {'assessments': [
            {'point': 1, 'status': 'supported', 'evidence': [{'candidate': 1, 'quote': '不同观测之间需要相互独立。'}]},
            {'point': 2, 'status': 'supported', 'evidence': [{'candidate': 2, 'quote': '达到阈值应拒绝假设。'}]},
        ]}
        result = assess(answer, ['观测的关系', '阈值用法'], rows)
        self.assertEqual([item['status'] for item in result], ['supported', 'untraceable'])

    def test_keeps_a_two_passage_bundle_together(self):
        rows = [row(1, 1, '低于阈值时执行第一个分支。'), row(2, 2, '高于阈值时执行第二个分支。')]
        checks = [{'status': 'supported', 'evidence': [{'candidate': 1}, {'candidate': 2}]}]
        self.assertEqual(select(checks, rows, len(rows[0]['text'])), [])
        self.assertEqual(select(checks, rows, sum(len(r['text']) for r in rows)), rows)

    def test_preserves_selected_evidence_and_skips_contained_short_passage(self):
        short = row(1, 3, '不同观测之间需要相互独立。')
        complete = row(2, 3, short['text'] + '同时应说明在什么条件下使用该分析方法。')
        supplement = row(3, 4, '接下来是另一个需要单独说明的条件。')
        checks = [{'status': 'supported', 'evidence': [{'candidate': 1}]},
                  {'status': 'supported', 'evidence': [{'candidate': 2}]}]
        budget = len(complete['text']) + len(supplement['text'])
        priority = select(checks, [short, complete, supplement], budget)
        self.assertEqual(priority, [complete])
        self.assertEqual(pack_verified(priority, [short, complete, supplement], budget), [complete, supplement])
