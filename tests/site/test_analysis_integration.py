import tempfile
import unittest
from pathlib import Path
from sitegen.build import build_site


class AnalysisIntegrationTests(unittest.TestCase):
    def test_glossary_has_contextual_analysis_link_and_explicit_additional_example(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_site('preview', root)
            page = (root/'terms/simple-linear-regression.html').read_text(encoding='utf-8')
            self.assertIn('../analyses/linear-simple.html', page)
            self.assertIn('看完整分析示例', page)
            self.assertIn('不同教学问题', page)

    def test_local_build_has_analysis_navigation_details_and_distinct_search(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = build_site('preview', root)
            self.assertTrue((root / 'analysis.html').exists(), 'analysis entry missing')
            self.assertTrue((root / 'analyses/describe.html').exists())
            self.assertTrue((root / 'analysis-code/describe.R').exists())
            self.assertIn('怎么看数据', (root / 'index.html').read_text(encoding='utf-8'))
            self.assertIn('"kind":"analysis"', (root / 'assets/data/site-data.js').read_text(encoding='utf-8'))
            self.assertEqual(len(list(root.rglob('*.html'))), report.page_count)
