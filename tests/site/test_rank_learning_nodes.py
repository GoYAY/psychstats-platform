import json
from pathlib import Path
import tempfile
import unittest

from sitegen.build import build_site


class RankLearningNodesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.output = Path(cls.directory.name) / 'preview'
        build_site('preview', cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_rank_dependencies_link_to_distinct_explanations(self):
        expected = {
            'degrees-of-freedom': 'matrix-rank.html',
            'spearman-correlation': 'data-rank.html',
            'multicollinearity': 'linear-dependence.html',
            'fixed-effect': 'design-matrix.html',
            'mahalanobis-distance': 'matrix-inverse.html',
            'wilks-lambda': 'determinant.html',
            'nonparametric-test': 'wilcoxon-rank-sum.html',
        }
        for source, target in expected.items():
            with self.subTest(source=source):
                page = (self.output / 'terms' / (source + '.html')).read_text(encoding='utf-8')
                self.assertIn('href="' + target + '"', page)
                self.assertTrue((self.output / 'terms' / target).exists())

    def test_supporting_concepts_are_searchable_anchor_targets(self):
        index = json.loads((self.output / 'assets/data/search-index.json').read_text(encoding='utf-8'))
        entries = index if isinstance(index, list) else index['terms']
        by_id = {item['id']: item for item in entries}
        for slug, name, anchor in [('matrix-rank', '满列秩', 'full-column-rank'),
                                   ('matrix-rank', '秩亏', 'rank-deficiency'),
                                   ('data-rank', '平均秩', 'average-rank')]:
            with self.subTest(name=name):
                self.assertEqual(by_id.get(slug, {}).get('concepts', {}).get(name), anchor)
                page = (self.output / 'terms' / (slug + '.html')).read_text(encoding='utf-8')
                self.assertIn('id="' + anchor + '"', page)

    def test_both_wilcoxon_designs_reach_practice_bank(self):
        bank = json.loads((self.output / 'assets/data/quiz-bank.json').read_text(encoding='utf-8'))
        ids = {item['term_id'] for item in bank}
        self.assertTrue({'wilcoxon-rank-sum', 'wilcoxon-signed-rank'} <= ids)


if __name__ == '__main__':
    unittest.main()
