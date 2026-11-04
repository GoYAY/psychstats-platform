import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class NextExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('next_export', ROOT/'tools/export_next_preview.py')
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.temp = tempfile.TemporaryDirectory(prefix='psy-next-test-')
        cls.output = Path(cls.temp.name)
        cls.manifest = cls.module.export_preview(cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_preserves_real_content_and_formula(self):
        for term, literal in [('variable', '想研究学习时间和考试焦虑的关系'), ('sem', '结构方程模型')]:
            html = (self.output/'generated'/self.manifest['pages'][term]['file']).read_text(encoding='utf-8')
            self.assertIn(literal, html)
            self.assertNotIn('<script', html)
            self.assertNotRegex(html, r'\son\w+=')
        sem = (self.output/'generated/sem.html').read_text(encoding='utf-8')
        self.assertIn('formula-symbol', sem)
        self.assertIn('quiz-result', sem)
        self.assertIn('<strong>', sem)

    def test_client_view_payloads_match_generated_content(self):
        for key in ('index', 'paths', 'variable', 'sem'):
            file = self.output / 'public/assets/data/views' / (key + '.json')
            self.assertTrue(file.is_file(), key + ' client payload missing')
            view = json.loads(file.read_text(encoding='utf-8'))
            self.assertEqual(view['key'], key)
            self.assertEqual(view['sourceHash'], self.manifest['sourceHash'])
            if key == 'index':
                self.assertEqual(len(view['payload']['terms']), 179)
                self.assertNotIn('search', view['payload'])
            else:
                self.assertEqual(view['payload']['html'], (self.output/'generated'/(key+'.html')).read_text(encoding='utf-8'))

    def test_complete_order_and_card_symbols(self):
        self.assertEqual(len(self.manifest['terms']), 179)
        self.assertEqual(self.manifest['topics'][0]['id'], 'foundations')
        self.assertEqual(self.manifest['terms'][0]['id'], 'variable')
        self.assertTrue(any('term-symbol-badge' in t['cardHtml'] for t in self.manifest['terms']))
        self.assertGreater(len(self.manifest['search']), 179)

    def test_does_not_repeat_full_text_in_every_card_payload(self):
        self.assertNotIn('body_text', self.manifest['terms'][0])
        search=json.loads((self.output/'public/assets/data/search-index.json').read_text(encoding='utf-8'))
        self.assertIn('想研究学习时间', search[0]['body_text'])

    def test_copies_only_needed_resources(self):
        self.assertTrue((self.output/'public/assets/site.css').is_file())
        self.assertTrue((self.output/'public/assets/vendor/katex/katex.min.css').is_file())
        self.assertTrue(list((self.output/'public/assets/vendor/katex/fonts').glob('*.woff2')))
        self.assertFalse((self.output/'public/assets/soft-navigation.js').exists())
        self.assertFalse((self.output/'public/analysis-logs/linear-simple.txt').exists())

    def test_rejects_missing_resource_and_escape(self):
        with self.assertRaises(FileNotFoundError):
            self.module.resource_path(self.output, 'missing.svg')
        with self.assertRaises(ValueError):
            self.module.resource_path(self.output, '../outside.svg')

    def test_has_explicit_preview_and_legacy_links(self):
        card = self.manifest['terms'][0]['cardHtml']
        self.assertIn('/psy-stats/terms/variable/', card)
        other = next(t for t in self.manifest['terms'] if t['id']=='measurement-scales')
        self.assertIn('http://127.0.0.1:8765/psy-stats/terms/measurement-scales.html', other['cardHtml'])
        self.assertEqual(self.manifest['schemaVersion'], 1)
        self.assertTrue(self.manifest['sourceHash'])


if __name__ == '__main__':
    unittest.main()
