import re
import unittest
from html import unescape
from tests.site import test_analysis_output_guides as fixtures


class StatisticalDisplayTests(unittest.TestCase):
    def test_small_p_is_thresholded_without_changing_other_small_values(self):
        from sitegen.statistical_display import format_p, normalize_p_text
        for p in [0, 1e-20, 0.0009999]:
            self.assertEqual('<0.001', format_p(p))
        self.assertEqual('0.001', format_p(0.001))
        self.assertEqual('B=2e-08，p < 0.001。', normalize_p_text('B=2e-08，p=3e-12。'))

    def test_console_formats_coefficient_p_and_emphasizes_estimate(self):
        from sitegen.statistical_display import console_html
        raw = '            Estimate Std. Error t value Pr(>|t|)\nstress      -0.48066    0.04996   -9.62   <2e-16 ***\n'
        rendered = console_html(raw)
        self.assertIn('<strong class="stat-significant">-0.48066</strong>', rendered)
        self.assertIn('&lt;0.001', rendered)
        self.assertNotIn('<strong class="stat-significant">0.04996', rendered)
        self.assertNotIn('2e-16', rendered)

    def test_parameter_table_has_small_p_format_and_significant_estimate(self):
        _, _, html = fixtures.OutputGuideTests().fixture('linear-simple')
        table = re.search(r'<table><caption>coefficients</caption>(.*?)</table>', html, re.S)[1]
        self.assertIn('&lt;0.001', table)
        self.assertIn('<strong class="stat-significant">-0.4807</strong>', table)
        self.assertNotIn('1.227e-19', table)

    def test_reproduction_hint_is_separate_from_design(self):
        _, _, html = fixtures.OutputGuideTests().fixture('sem')
        design = re.search(r'<section(?: [^>]*)?><h2>这次分析了什么</h2>(.*?)</section>', html, re.S)[1]
        self.assertNotIn('固定种子', design)
        self.assertRegex(html, r'<aside class="analysis-reproduction-note".*?固定种子')

    def test_corrected_p_controls_emphasis(self):
        from sitegen.statistical_display import significant_row, significant_columns
        row = {'difference':2.0, 'p':0.03, 'p_holm':0.08, 'se':0.001}
        self.assertFalse(significant_row(row))
        row['p_holm'] = 0.04
        self.assertTrue(significant_row(row))
        self.assertEqual({'difference','p_holm'}, significant_columns(row))

    def test_report_emphasizes_significant_values_not_a_nonsignificant_p(self):
        from sitegen.statistical_display import significant_phrases
        self.assertIn('B=0.42', significant_phrases('B=0.42（SE=0.1，p=0.002）。'))
        self.assertEqual([], significant_phrases('B=0.42（SE=0.1，p=0.2）。'))

    def test_lower_bound_is_not_rewritten_as_an_upper_bound(self):
        from sitegen.statistical_display import normalize_p_text, console_html
        self.assertEqual('p > 0.00001', normalize_p_text('p > 0.00001'))
        self.assertIn('0.00001', console_html('p-value > 0.00001'))

    def test_raw_p_does_not_bold_a_result_with_nonsignificant_adjusted_p(self):
        from sitegen.statistical_display import significant_phrases
        self.assertEqual([],significant_phrases('B=0.42，p=0.03，p_holm=0.08。'))

    def test_vertical_fit_measure_p_is_formatted_by_its_row_label(self):
        from sitegen.statistical_display import governing_p, significant_columns
        row={'index':'pvalue.scaled','value':0.000001}
        self.assertEqual('value',governing_p(row))
        self.assertEqual({'value'},significant_columns(row))

    def test_vertical_fit_measure_p_is_thresholded_in_actual_page(self):
        case,result,_=fixtures.OutputGuideTests().fixture('cfa')
        from sitegen.analysis_reader import render_analysis_case
        result['tables']['fit']=[{'index':'pvalue.scaled','value':0.000001},*result['tables']['fit']]
        html=render_analysis_case(case,result,{})
        self.assertRegex(html,r'pvalue\.scaled</td><td[^>]*><strong class="stat-significant">&lt;0\.001</strong>')
