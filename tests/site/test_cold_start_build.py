import hashlib,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

class ColdStartBuildTests(unittest.TestCase):
    def test_opt_in_startup_bundle_is_versioned_offline_and_uses_shared_core(self):
        from tools.prepare_local_library_preview import prepare_preview
        with tempfile.TemporaryDirectory(dir=ROOT/'site',prefix='cold-build-test-') as d:
            folder=Path(d);base=folder/'base';base.mkdir()
            (base/'index.html').write_text('<html><head></head><body></body></html>')
            # A minimal library entry allows checking its complete offline manifest.
            (base/'datasets.html').write_text('<html><head></head><body><nav aria-label="主导航"></nav><main></main></body></html>',encoding='utf-8')
            report=prepare_preview(base,folder/'candidate',bundle_library=True)
            directory=report['moduleDirectory'];entry=report['libraryEntry'];output=folder/'candidate'
            self.assertEqual(entry,'app-boot.mjs')
            self.assertIn(directory+'/'+entry,(output/'library/index.html').read_text(encoding='utf-8'))
            self.assertTrue((output/'assets'/directory/entry).is_file())
            manifest=json.loads((output/'library/offline-manifest.json').read_bytes())
            row=next(r for r in manifest['resources'] if r['url']=='../assets/'+directory+'/'+entry)
            self.assertEqual(row['hash'],hashlib.sha256((output/'assets'/directory/entry).read_bytes()).hexdigest())
            # Lazy readers still consume the same original, versioned core files.
            self.assertIn('../'+report['chartCoreDirectory']+'/',(output/'assets'/directory/'reader.mjs').read_text(encoding='utf-8'))

    def test_bundling_changes_runtime_without_rewriting_baseline(self):
        from tools.prepare_local_library_preview import prepare_preview
        with tempfile.TemporaryDirectory(dir=ROOT/'site',prefix='cold-build-test-') as d:
            folder=Path(d);base=folder/'base';base.mkdir();original=b'<html><head></head><body></body></html>'
            (base/'index.html').write_bytes(original)
            old=prepare_preview(base,folder/'old');new=prepare_preview(base,folder/'new',bundle_library=True)
            self.assertNotEqual(old['runtimeVersion'],new['runtimeVersion'])
            self.assertEqual((base/'index.html').read_bytes(),original)
