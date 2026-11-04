import json
import unittest
from pathlib import Path
from sitegen import analysis_catalog

ROOT=Path(__file__).resolve().parents[2]

class AnalysisExampleSelectionTests(unittest.TestCase):
    def test_specific_correlation_term_uses_its_own_method_first(self):
        self.assertTrue(hasattr(analysis_catalog,'select_analysis_examples'))
        cases=analysis_catalog.load_analysis_cases(ROOT/'site/content/analysis_cases')
        catalog=json.loads((ROOT/'site/content/analysis_catalog.json').read_text(encoding='utf-8'))
        for term,want in [('spearman-correlation','correlation'),('correlation-coefficient','correlation'),('partial-correlation','correlation-types'),('simple-linear-regression','linear-simple')]:
            route=next(r for r in catalog['term_routes'] if r['term_id']==term)
            self.assertEqual(analysis_catalog.select_analysis_examples(term,route,cases)[0]['id'],want)

    def test_other_multi_example_terms_prefer_the_named_method_over_file_order(self):
        cases=analysis_catalog.load_analysis_cases(ROOT/'site/content/analysis_cases')
        catalog=json.loads((ROOT/'site/content/analysis_catalog.json').read_text(encoding='utf-8'))
        expected={'multiple-regression':'linear','cronbach-alpha':'reliability',
                  'internal-consistency':'reliability','mcdonald-omega':'reliability-omega',
                  'reliability':'reliability','fisher-exact-test':'categorical',
                  'interaction':'factorial-blocks','robust-standard-errors':'diagnostics',
                  'sensitivity-analysis':'diagnostics','data-cleaning':'diagnostics',
                  'repeated-measures':'repeated','sphericity':'repeated',
                  'stepwise-regression':'selection','t-test':'t-tests',
                  'confidence-interval':'intervals','wilcoxon-rank-sum':'ranks',
                  'wilcoxon-signed-rank':'ranks'}
        for term,want in expected.items():
            with self.subTest(term=term):
                route=next(r for r in catalog['term_routes'] if r['term_id']==term)
                self.assertEqual(analysis_catalog.select_analysis_examples(term,route,cases)[0]['id'],want)
