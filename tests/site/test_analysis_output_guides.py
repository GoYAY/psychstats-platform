import json
import re
import unittest
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class OutputGuideTests(unittest.TestCase):
    def test_output_and_meaning_use_the_linked_term_topic(self):
        from sitegen.analysis_reader import render_analysis_case
        case, result, _ = self.fixture('linear-simple')
        html = render_analysis_case(case, result, {},
                                    {'intercept':'regression', 'simple-linear-regression':'regression'},
                                    'regression')
        self.assertRegex(html, r'class="analysis-field[^>]*data-topic="regression"[^>]*data-analysis-source="intercept"')
        self.assertRegex(html, r'class="analysis-meaning"[^>]*data-topic="regression"[^>]*data-analysis-meaning="intercept"')
        self.assertIn('data-analysis-case="linear-simple" data-topic="regression"', html)

    def test_new_top_level_pages_use_shared_page_heading(self):
        from sitegen.analysis_reader import render_analysis_index
        from sitegen.symbol_reference import render_reference
        for html in [render_analysis_index({'units':[]}, {}), render_reference([], {})]:
            self.assertRegex(html, r'<section class="page-head"><h1>')

    def fixture(self, slug):
        from sitegen.analysis_reader import render_analysis_case
        case = json.loads((ROOT/'site/content/analysis_cases'/f'{slug}.json').read_text(encoding='utf-8'))
        result = json.loads((ROOT/'site/content/analysis_results'/f'{slug}.json').read_text(encoding='utf-8'))
        return case, result, render_analysis_case(case, result, {})

    def test_regression_teaches_the_original_coefficient_cells(self):
        _, _, html = self.fixture('linear-simple')
        primary = html.split('class="analysis-console"')[0]
        self.assertRegex(primary, r'data-analysis-field="intercept"[^>]*><strong class="stat-significant">71\.49525</strong></button>')
        self.assertRegex(primary, r'data-analysis-field="slope"[^>]*><strong class="stat-significant">-0\.48066</strong></button>')
        self.assertIn('Coefficients', primary)
        self.assertIn('Estimate', primary)
        self.assertIn('定位到输出', primary)

    def test_descriptive_guide_targets_actual_r_vector_values(self):
        _, _, html = self.fixture('describe')
        primary = html.split('class="analysis-console"')[0]
        self.assertRegex(primary, r'data-analysis-field="mean"[^>]*>48\.610556</button>')
        self.assertRegex(primary, r'data-analysis-field="sd"[^>]*>8\.064545</button>')
        self.assertIn('数值越大，分数越分散', html)
        self.assertNotIn('不是平均数的不确定性', html)

    def test_lavaan_guide_targets_exported_fit_measure(self):
        _, _, html = self.fixture('cfa')
        self.assertIn('data-analysis-source="cfi"', html)
        self.assertIn('cfi.scaled', html)

    def test_diagnostic_advice_is_always_open(self):
        _, _, html = self.fixture('describe')
        self.assertNotIn('<details class="analysis-diagnosis"', html)
        self.assertIn('<section class="analysis-diagnosis"', html)

    def test_locale_warning_explains_user_impact_and_keeps_raw_log(self):
        _, result, html = self.fixture('describe')
        self.assertIn('字符', html)
        self.assertIn('本次分析已完成', html)
        self.assertIn(unescape('Setting LC_COLLATE=C.UTF-8 failed'), unescape(html))
        self.assertEqual(0, result['exit_code'])

    def test_report_is_a_result_paragraph_with_real_estimates(self):
        from sitegen.analysis_reader import report_text
        case, result, _ = self.fixture('linear-simple')
        report = report_text(case, result)
        self.assertIn('-0.481', report)
        self.assertIn('0.205', report)
        self.assertNotRegex(report, '因果|不能|而非|不证明')

    def test_all_fields_have_a_visible_source_and_location(self):
        for path in (ROOT/'site/content/analysis_cases').glob('*.json'):
            with self.subTest(case=path.stem):
                case, result, html = self.fixture(path.stem)
                for a in case['annotations']:
                    self.assertIn('data-analysis-source="'+a['field_id']+'"', html)
                # Full displayed console retains structure; raw evidence is downloadable.
                console = re.search(r'<details class="analysis-console".*?<pre>(.*?)</pre>', html, re.S)
                self.assertIsNotNone(console)
                visible = unescape(re.sub('<[^>]+>','',console[1]))
                self.assertEqual(result['stdout'].count('\n'),visible.count('\n'))
                self.assertIn('../analysis-logs/'+case['id']+'.txt',html)
