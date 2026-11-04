import importlib.util
import inspect
import json
import tempfile
import shutil
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def module_at(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NextCompatibilityTests(unittest.TestCase):
    def test_formula_preparation_declares_only_fonts_used_by_rendered_formula(self):
        module = module_at('font_compat_export', 'tools/export_next_preview.py')
        with tempfile.TemporaryDirectory() as folder:
            manifest = module.export_preview(Path(folder), source_root=ROOT/'site/dist')
            fonts = manifest['pages']['term:sem'].get('formulaFonts', [])
            self.assertEqual({f['font'] for f in fonts}, {'normal 400 16px "KaTeX_Main"', 'normal 700 16px "KaTeX_Main"', 'italic 700 16px "KaTeX_Math"'})
            self.assertTrue(any('η' in f['text'] for f in fonts))
            self.assertEqual(manifest['pages']['term:variable'].get('formulaFonts', []), [])
    def test_first_picture_retains_media_alternatives_and_desktop_fallback(self):
        module = module_at('picture_compat_export', 'tools/export_next_preview.py')
        with tempfile.TemporaryDirectory() as folder:
            manifest = module.export_preview(Path(folder), source_root=ROOT/'site/dist')
            picture = manifest['pages']['term:sem']['firstScreenResources'][0]
            self.assertIn('/sem.svg?v=', picture['url'])
            self.assertIn('/sem-mobile.svg?v=', picture['sources'][0]['url'])
            self.assertEqual(picture['sources'][0]['media'], '(max-width: 600px)')

    def test_asset_only_changes_invalidate_build_and_versioned_resource_urls(self):
        module = module_at('asset_compat_export', 'tools/export_next_preview.py')
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            seed = module.export_preview(base/'seed', source_root=ROOT/'site/dist')
            source = base/'source'
            names = {'assets/data/site-data.js'} | {p['sourcePath'] for p in seed['pages'].values()}
            names.update(u.removeprefix('/psy-stats/').split('?')[0] for u in seed['pages']['index']['resources'])
            for name in names:
                target = source/name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT/'site/dist'/name, target)
            first = module.export_preview(base/'first', source_root=source)
            css = source/'assets/site.css'
            css.write_text(css.read_text(encoding='utf-8')+'\n/* asset-only update */', encoding='utf-8')
            second = module.export_preview(base/'second', source_root=source)
            self.assertNotEqual(first['buildHash'], second['buildHash'])
            self.assertNotEqual(first['assetURLs']['assets/site.css'], second['assetURLs']['assets/site.css'])
            self.assertIn('?v=', second['assetURLs']['assets/site.css'])
            self.assertEqual(len(second['pages']['term:sem']['firstScreenResources']), 1)

    def test_representative_payload_preserves_source_blocks(self):
        module = module_at('compat_export', 'tools/export_next_preview.py')
        self.assertIn('source_root', inspect.signature(module.export_preview).parameters)
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            manifest = module.export_preview(output, source_root=ROOT/'site/dist')
            self.assertEqual(manifest['schemaVersion'], 2)
            self.assertEqual(manifest['scope'], 'representative')
            self.assertIn('term:sem', manifest['pages'])
            record = manifest['pages']['term:sem']
            view = json.loads((output/'public'/record['payloadURL'].removeprefix('/psy-stats/')).read_text(encoding='utf-8'))
            self.assertEqual(view['buildHash'], manifest['buildHash'])
            self.assertEqual(view['key'], 'term:sem')
            html = ''.join(block['html'] for block in view['payload']['blocks'])
            self.assertIn('formula-symbol', html)
            self.assertIn('quiz-result', html)
            self.assertIn('结构方程模型', html)
            self.assertNotIn('<script', html)
            self.assertIn('/psy-stats/terms/sem.html', [x['path'] for x in record['aliases']])
            self.assertEqual(len(manifest['terms']), 179)
            self.assertNotIn('body_text', manifest['terms'][0])
            self.assertFalse((output/'public/assets/soft-navigation.js').exists())

    def test_compatibility_entries_contain_correct_initial_view(self):
        path = ROOT/'tools/finalize_next_export.py'
        self.assertTrue(path.exists(), 'static compatibility finalizer missing')
        module = module_at('compat_finalize', 'tools/finalize_next_export.py')
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            page = output/'terms/sem/index.html'
            page.parent.mkdir(parents=True)
            page.write_text('<main><h1>结构方程模型</h1><p>term:sem</p></main>', encoding='utf-8')
            manifest = {'pages': {'term:sem': {'canonicalPath': '/psy-stats/terms/sem/', 'aliases': [{'path': '/psy-stats/terms/sem.html'}]}}}
            result = module.finalize_export(output, manifest)
            self.assertEqual(result['aliases'], 1)
            self.assertEqual((output/'terms/sem.html').read_bytes(), page.read_bytes())
            manifest['pages']['term:sem']['aliases'] = [{'path': '/psy-stats/../../outside.html'}]
            with self.assertRaises(ValueError):
                module.finalize_export(output, manifest)
