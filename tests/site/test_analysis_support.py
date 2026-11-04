import json
import unittest
from pathlib import Path
from html import unescape

ROOT = Path(__file__).resolve().parents[2]


class AnalysisSupportTests(unittest.TestCase):
    def test_authored_support_covers_the_exact_analysis_catalog(self):
        support = json.loads((ROOT / 'site/content/analysis_support.json').read_text(encoding='utf-8'))
        expected = {p.stem for p in (ROOT / 'site/content/analysis_cases').glob('*.json')}
        self.assertEqual(set(support['cases']), expected)
        for item in support['cases'].values():
            self.assertLessEqual(set(item.get('variable_sets', [])), set(support['variable_sets']))

    def fixture(self, slug):
        return tuple(json.loads((ROOT / f'site/content/{folder}/{slug}.json').read_text(encoding='utf-8'))
                     for folder in ('analysis_cases', 'analysis_results'))

    def test_every_saved_analysis_has_visible_variable_correspondence_and_specific_diagnostics(self):
        from sitegen.output_guides import guides
        from sitegen.analysis_reader import render_analysis_case
        for path in (ROOT / 'site/content/analysis_cases').glob('*.json'):
            with self.subTest(case=path.stem):
                support = guides()[path.stem]
                self.assertTrue(support.get('variable_map'))
                self.assertGreaterEqual(len(support.get('diagnostics', [])), 2)
                case, result = self.fixture(path.stem)
                html = render_analysis_case(case, result, {})
                design = html.split('id="analysis-design"', 1)[1].split('id="analysis-output"', 1)[0]
                self.assertIn('analysis-variable-map', design)
                for row in support['variable_map']:
                    self.assertIn(row['zh'], unescape(design))
                    self.assertIn(row['code'], unescape(design))
                    self.assertTrue(row['role'])
                diagnoses = html.split('id="analysis-diagnostics"', 1)[1].split('id="paper-results"', 1)[0]
                self.assertNotIn('<details', diagnoses)
                for item in support['diagnostics']:
                    self.assertTrue(item['condition'])
                    self.assertTrue(item['action'])
                    self.assertIn(item['condition'], unescape(diagnoses))
                    self.assertIn(item['action'], unescape(diagnoses))

    def test_mediation_location_preserves_actual_r_selector_and_explains_label(self):
        from sitegen.output_guides import source_map, guides
        from sitegen.analysis_reader import render_analysis_case
        case, result = self.fixture('mediation')
        sources = source_map(case, result)
        row = result['tables']['parameters'][sources['direct']['row']]
        self.assertEqual((row['lhs'], row['op'], row['rhs'], row['label']),
                         ('well_being', '~', 'stress', 'c'))
        self.assertEqual(sources['direct']['column'], 'est')
        self.assertIn('well_being ~ stress', sources['direct']['location'])
        self.assertIn('c′', sources['direct']['location'])
        html = render_analysis_case(case, result, {})
        self.assertIn('社会支持', html)
        self.assertIn('social_support', html)
        self.assertIn('Bootstrap', html)
        self.assertNotIn('何时不能这样解释', html)
        self.assertNotIn('路径或交互不显著怎么办', html)
        # Explanatory overlay leaves recorded evidence and its fingerprint valid.
        from sitegen.analysis_catalog import validate_result
        self.assertEqual(validate_result(case, result), [])

    def test_variable_map_and_diagnostics_escape_text(self):
        from sitegen.output_guides import guides
        from sitegen.analysis_reader import render_analysis_case
        case, result = self.fixture('mediation')
        guide = guides()['mediation']
        old_map, old_diagnostics = guide['variable_map'], guide['diagnostics']
        try:
            guide['variable_map'] = [{'zh': '<script>alert(1)</script>', 'code': 'x<y', 'role': 'a&b'}]
            guide['diagnostics'] = [{'title': '<img>', 'condition': 'x<y', 'action': 'a&b'}]
            html = render_analysis_case(case, result, {})
            self.assertNotIn('<script>alert(1)</script>', html)
            self.assertIn('&lt;script&gt;', html)
            self.assertIn('x&lt;y', html)
            self.assertIn('a&amp;b', html)
        finally:
            guide['variable_map'], guide['diagnostics'] = old_map, old_diagnostics

    def test_overlay_merges_meanings_and_keeps_source_selectors(self):
        from sitegen.output_guides import guides
        original = json.loads((ROOT / 'site/content/analysis_guides.json').read_text(encoding='utf-8'))
        for slug, item in original.items():
            with self.subTest(case=slug):
                for field, selector in item.get('sources', {}).items():
                    for key, value in selector.items():
                        if key != 'location':
                            self.assertEqual(guides()[slug]['sources'][field][key], value)
                self.assertLessEqual(set(item.get('meanings', {})), set(guides()[slug].get('meanings', {})))
