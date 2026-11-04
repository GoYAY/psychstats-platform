import importlib.util
import subprocess
import unittest
import tempfile
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

class SoftNavigationTests(unittest.TestCase):
    def test_node_navigation_rules(self):
        result = subprocess.run(['node', '--test', 'tests/js/soft-navigation.test.mjs'], cwd=ROOT,
                                capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_preview_paths_are_bounded(self):
        spec = importlib.util.spec_from_file_location('preview_http', ROOT/'tools/preview_http.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        base = ROOT/'site/dist'
        self.assertEqual(module.resolve_path(base, '/psy-stats/index.html'), base.resolve()/'index.html')
        self.assertEqual(module.resolve_path(base, '/index.html'), base.resolve()/'index.html')
        for path in ['/../secret', '/psy-stats/%2e%2e/secret', '/%5c..%5csecret']:
            self.assertIsNone(module.resolve_path(base, path))

    def test_built_pages_share_runtime_version_and_correct_module_order(self):
        from sitegen.build import build_site
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            build_site('preview', output)
            versions = set()
            for name in ['index.html', 'terms/sem.html', 'symbols.html', 'analyses/mediation.html']:
                html = (output/name).read_text(encoding='utf-8')
                versions.add(re.search(r'name="psych-runtime" content="([a-f0-9]+)"', html).group(1))
                for asset in ['navigation-policy.js', 'page-runtime.js', 'navigation-motion.js', 'soft-navigation.js']:
                    self.assertEqual(html.count(asset+'?v='), 1)
                self.assertLess(html.index('page-runtime.js'), html.index('assets/site.js'))
                self.assertLess(html.index('navigation-motion.js'), html.index('soft-navigation.js'))
                self.assertTrue((output/'assets/soft-navigation.js').exists())
            self.assertEqual(len(versions), 1)
