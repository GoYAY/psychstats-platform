import importlib
from pathlib import Path
import tempfile
import unittest

class LocalLibraryPreviewTests(unittest.TestCase):
    def builder(self):
        try:return importlib.import_module('tools.prepare_local_library_preview')
        except ModuleNotFoundError:self.fail('Isolated preview builder is not implemented')

    def test_preview_refuses_protected_or_overlapping_output(self):
        builder=self.builder();root=Path(__file__).resolve().parents[2]
        for target in [root/'site/dist',root/'site/paper-table-audit-preview',root/'site',root/'site/paper-table-audit-preview/nested']:
            with self.subTest(target=target),self.assertRaises(ValueError):builder.prepare_preview(root/'site/paper-table-audit-preview',target)

    def test_baseline_is_read_only_and_private_fixtures_are_not_copied(self):
        builder=self.builder();root=Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory(dir=root/'site',prefix='library-preview-test-') as d:
            folder=Path(d);base=folder/'baseline';base.mkdir();(base/'index.html').write_text('<html><head></head><body>baseline</body></html>')
            before=(base/'index.html').read_bytes();out=folder/'output'
            report=builder.prepare_preview(base,out)
            self.assertEqual((base/'index.html').read_bytes(),before)
            self.assertTrue((out/'qa/library-host.html').exists())
            self.assertFalse((out/'private-fixtures').exists())
            self.assertEqual(report['privateFilesCopied'],0)

    def test_entry_is_added_with_versioned_modules_and_narrow_public_route(self):
        builder=self.builder();root=Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory(dir=root/'site',prefix='library-preview-test-') as d:
            out=Path(d)/'output';report=builder.prepare_preview(root/'site/paper-table-audit-preview',out)
            page=(out/'library/index.html').read_text(encoding='utf-8')
            self.assertIn('data-library-root',page)
            self.assertIn('我的知识库',(out/'index.html').read_text(encoding='utf-8'))
            self.assertIn('moduleDirectory',report)
            self.assertTrue((out/'assets'/report['moduleDirectory']/'app.mjs').is_file())
            self.assertNotIn('data-library-root',(out/'index.html').read_text(encoding='utf-8'))

    def test_cursor_fix_is_shipped_and_versioned_without_changing_baseline(self):
        builder=self.builder();root=Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory(dir=root/'site',prefix='library-preview-test-') as d:
            base=Path(d)/'baseline';(base/'assets').mkdir(parents=True)
            (base/'index.html').write_text('<html><head></head><body><script src="assets/cursor.js?v=old"></script></body></html>')
            (base/'assets/cursor.js').write_text('/* old cursor */')
            out=Path(d)/'output';report=builder.prepare_preview(base,out)
            self.assertEqual((base/'assets/cursor.js').read_text(),'/* old cursor */')
            self.assertEqual((out/'assets/cursor.js').read_bytes(),(root/'site/assets/cursor.js').read_bytes())
            self.assertIn('cursor.js',report['changedRuntimeAssets'])
            self.assertNotIn('cursor.js?v=old',(out/'index.html').read_text())

if __name__=='__main__':unittest.main()
