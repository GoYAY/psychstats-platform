import importlib.util
import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class VisibleDisplays(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.displays = []
        self.rows = []
        self.current_table = None

    def handle_starttag(self, tag, attrs):
        if tag == 'details':
            self.depth += 1
        if not self.depth and tag in ('figure', 'table'):
            self.displays.append(tag)
        if not self.depth and tag == 'table':
            self.rows.append(0)
            self.current_table = len(self.rows)-1
        if not self.depth and tag == 'tr' and self.current_table is not None:
            self.rows[self.current_table] += 1

    def handle_endtag(self, tag):
        if tag == 'details':
            self.depth -= 1
        if tag == 'table':
            self.current_table = None


class CompactAnalysisTests(unittest.TestCase):
    def fixture(self, slug):
        return tuple(json.loads((ROOT / f'site/content/{folder}/{slug}.json').read_text(encoding='utf-8'))
                     for folder in ('analysis_cases', 'analysis_results'))

    def test_one_primary_display_with_supplementary_data_preserved(self):
        from sitegen.paper_reporting import render_paper_result
        for path in (ROOT / 'site/content/analysis_cases').glob('*.json'):
            html = render_paper_result(*self.fixture(path.stem))
            parser = VisibleDisplays()
            parser.feed(html)
            self.assertEqual(len(parser.displays), 1, path.stem)
            self.assertIn('download', html)
            if path.stem == 'mediation':
                self.assertEqual(parser.displays, ['figure'])
                self.assertIn('完整路径与测量参数', html)
            if path.stem == 'moderation':
                self.assertIn('moderation-slopes.svg', html)

    def test_output_precedes_paper_and_navigation_targets_exist(self):
        from sitegen.analysis_reader import render_analysis_case
        html = render_analysis_case(*self.fixture('mediation'), {})
        headings = re.findall(r'<h2[^>]*>(.*?)</h2>', html)
        self.assertLess(headings.index('真实运行输出'), headings.index('论文式结果图表'))
        self.assertLess(headings.index('遇到这种结果怎么办'), headings.index('论文式结果图表'))
        self.assertIn('class="analysis-toc"', html)
        targets = re.findall(r'data-analysis-section href="#([^"]+)"', html)
        self.assertEqual(len(targets), 6)
        for target in targets:
            self.assertEqual(html.count(f'id="{target}"'), 1)

    def test_mediation_uses_triangle_instead_of_detour(self):
        spec = importlib.util.spec_from_file_location('paper_figures_test', ROOT / 'tools/render_paper_results.py')
        renderer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(renderer)
        from sitegen.paper_reporting import paper_data
        data = paper_data(*self.fixture('mediation'))
        fig = renderer.model_figure(data, '#953970')
        try:
            positions = {label.get_text(): label.get_position() for label in fig.axes[0].texts}
            x, m, y = (positions[name] for name in ('压力', '社会支持', '幸福感'))
            self.assertLess(x[0], m[0])
            self.assertLess(m[0], y[0])
            self.assertEqual(x[1], y[1])
            self.assertGreater(m[1], x[1])
            self.assertTrue(any('间接效应' in label.get_text() and 'CI' in label.get_text()
                                for label in fig.axes[0].texts))
        finally:
            renderer.plt.close(fig)

    def test_large_software_tables_keep_key_fields_visible_and_rest_expandable(self):
        from sitegen.analysis_reader import render_analysis_case
        html = render_analysis_case(*self.fixture('cfa'), {})
        output = re.search(r'<section id="analysis-output">(.*?)</section>',html,re.S)[1]
        parser = VisibleDisplays()
        parser.feed(output)
        self.assertTrue(parser.rows)
        self.assertTrue(all(count <= 25 for count in parser.rows), parser.rows)
        self.assertIn('其余', output)
        self.assertIn('data-analysis-source="cfi"', output)
        self.assertIn('baseline.chisq', output)


if __name__ == '__main__':
    unittest.main()
