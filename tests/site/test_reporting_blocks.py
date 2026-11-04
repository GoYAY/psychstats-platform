import unittest
from sitegen.render import render_term
from tests.site.test_rendered_pages import sample_term


class ReportingBlockTests(unittest.TestCase):
    def test_specific_report_and_limits_are_escaped_and_rendered(self):
        term = sample_term()
        term['r_practice'].update(report_template='填写均值与区间',
                                  report_example='教学数据：M=2；x < 3',
                                  report_limits=['不能证明因果'])
        html = render_term(term, preview=True)
        self.assertIn('研究结果怎么写', html)
        self.assertIn('填写均值与区间', html)
        self.assertIn('教学数据：M=2；x &lt; 3', html)
        self.assertIn('使用与解释时的检查', html)
        self.assertLess(html.index('使用与解释时的检查'), html.index('研究结果怎么写'))
        self.assertNotIn('不能证明因果', html[html.index('<aside class="report-example"'):html.index('</aside>', html.index('<aside class="report-example"'))])
        self.assertIn('不能证明因果', html)

    def test_old_page_without_report_has_no_empty_heading(self):
        html = render_term(sample_term(), preview=True)
        self.assertNotIn('研究结果怎么写', html)
        self.assertNotIn('不要据此下结论', html)

    def test_generic_template_is_not_a_specific_example(self):
        term = sample_term()
        term['r_practice']['report_template'] = '报告估计量、区间、研究设计和诊断。'
        html = render_term(term, preview=True)
        self.assertNotIn('教学数据报告示例', html)
