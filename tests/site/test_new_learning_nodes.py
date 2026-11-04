import json
from pathlib import Path
import unittest
from sitegen.model import term_from_dict, validate_term
from sitegen.render import render_term

ROOT = Path(__file__).resolve().parents[2] / 'site/content'
GROUPS = {
    'measurement': ['reliability','internal-consistency','cronbach-alpha','mcdonald-omega','validity','measurement-invariance'],
    'exploration': ['parallel-analysis','polychoric-correlation','spearman-correlation','partial-correlation'],
    'planning': ['sample-size-planning','sesoi','equivalence-testing','welch-anova','planned-contrast','fisher-exact-test'],
    'diagnostics': ['reverse-scoring','scale-scoring','sensitivity-analysis','heteroscedasticity','robust-standard-errors','cross-validation','confounding'],
}


class NewLearningNodesTests(unittest.TestCase):
    def check_group(self, group):
        registry = json.loads((ROOT/'registry.json').read_text(encoding='utf-8'))['terms']
        ids = {term['id'] for term in registry}
        for slug in GROUPS[group]:
            with self.subTest(term=slug):
                path = ROOT/'drafts'/f'{slug}.json'
                self.assertTrue(path.exists(), f'Missing learning node {slug}')
                term = json.loads(path.read_text(encoding='utf-8'))
                self.assertEqual(validate_term(term_from_dict(term)), [])
                html = render_term(term, preview=True, available_ids=ids)
                self.assertEqual(html.count('class="option-feedback"'),4)
                self.assertLess(html.index('你可能会问'), html.index('操作性定义'))
                self.assertTrue(term.get('plain_example'))
                self.assertGreaterEqual(len(term.get('sections',[])),2)
                self.assertTrue(any(slug in targets for other in registry if other['id']!=slug for targets in other['relations'].values()), 'Missing inbound relation')
                for targets in term['relations'].values():
                    self.assertTrue(set(targets)<=ids)
                self.assertEqual(term['status'],'draft')

    def test_measurement(self): self.check_group('measurement')
    def test_exploration(self): self.check_group('exploration')
    def test_planning(self): self.check_group('planning')
    def test_diagnostics(self): self.check_group('diagnostics')
