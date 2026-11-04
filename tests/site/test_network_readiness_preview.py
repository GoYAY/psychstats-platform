import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
try:
    from tools import prepare_network_readiness_preview as preview
except ImportError:
    preview=None

class NetworkReadinessPreviewTests(unittest.TestCase):
    def test_custom_source_cannot_overwrite_default_distribution(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'site/source';output=root/'site/dist'
            source.mkdir(parents=True);output.mkdir()
            for path in (root/'site/next-preview/lib/page-resources.mjs',
                         root/'site/experiments/critical-resources-bridge.mjs',
                         source/'assets/vendor/katex/katex.min.css'):
                path.parent.mkdir(parents=True,exist_ok=True);path.write_text('',encoding='utf-8')
            (output/'keep.txt').write_text('accepted',encoding='utf-8')
            with patch.object(preview,'ROOT',root):
                with self.assertRaises(ValueError):
                    preview.prepare(output,source=source)
            self.assertEqual((output/'keep.txt').read_text(encoding='utf-8'),'accepted')

    def test_explicit_source_builds_independently_and_content_changes_release(self):
        with tempfile.TemporaryDirectory(dir=preview.ROOT/'site', prefix='table-preview-test-') as folder:
            root=Path(folder);source=root/'source';output=root/'output'
            (source/'assets/vendor/katex').mkdir(parents=True)
            (source/'assets/vendor/katex/katex.min.css').write_text('',encoding='utf-8')
            html='<html><head><meta name="psych-runtime" content="old"><script src="assets/soft-navigation.js?v=old"></script></head><body><main>FIRST</main></body></html>'
            (source/'index.html').write_text(html,encoding='utf-8')
            preview.prepare(output,navigation=True,source=source)
            first=(output/'index.html').read_text(encoding='utf-8')
            self.assertIn('FIRST',first)
            self.assertIn('data-psych-resource-hints',first)
            (source/'index.html').write_text(html.replace('FIRST','SECOND'),encoding='utf-8')
            preview.prepare(output,navigation=True,source=source)
            second=(output/'index.html').read_text(encoding='utf-8')
            import re
            release=lambda text:re.search('name="psych-runtime" content="([^"]+)',text)[1]
            self.assertNotEqual(release(first),release(second),'Updated content must not share a mixed-release navigation cache')
            self.assertIn('SECOND',second)

    def test_link_hints_cover_visible_and_later_links_but_exclude_external_and_downloads(self):
        self.assertTrue(hasattr(preview, 'linked_resource_hints'), 'Linked critical resource hints are missing')
        html='<main><a href="../terms/sem.html#formula">SEM</a><a href="https://outside.test/terms/sem.html">external</a><a href="../terms/sem.html" download>download</a><a href="../terms/later.html">later</a></main>'
        records={'terms/sem.html':{'firstScreenResources':[{'kind':'image','url':'../assets/sem.svg'}],'formulaFonts':[]},'terms/later.html':{'firstScreenResources':[],'formulaFonts':[{'font':'16px "KaTeX_Main"','text':'x'}]}}
        self.assertEqual(preview.linked_resource_hints(html,'topics/start.html',records),records)

    def test_record_preserves_desktop_fallback_and_only_first_illustration(self):
        self.assertIsNotNone(preview, 'Critical resource records are not implemented')
        html='<main><article class="term-content"><picture><source media="(max-width:600px)" srcset="../assets/mobile.svg"><img src="../assets/desktop.svg"></picture><img src="../assets/later.svg"></article></main>'
        record=preview.critical_record(html, '')
        self.assertEqual(record['firstScreenResources'], [{'kind':'image','url':'../assets/desktop.svg','sources':[{'media':'(max-width:600px)','url':'../assets/mobile.svg'}]}])
        self.assertEqual(record['formulaFonts'], [])

    def test_record_uses_rendered_formula_text_without_mathml(self):
        self.assertIsNotNone(preview, 'Critical resource records are not implemented')
        html='<main><span class="katex"><span class="katex-mathml">not-rendered</span><span class="katex-html"><span class="mathnormal">x</span></span></span></main>'
        css='.katex .mathnormal{font-family:KaTeX_Math;font-style:italic;font-weight:400;}'
        self.assertEqual(preview.critical_record(html, css)['formulaFonts'], [{'font':'italic 400 16px "KaTeX_Math"','text':'x'}])
