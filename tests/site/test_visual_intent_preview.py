import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]

class VisualIntentPreviewTests(unittest.TestCase):
    def test_new_builder_rejects_all_other_targets_before_copy(self):
        try:from tools.prepare_visual_intent_preview import prepare
        except ImportError:self.fail('isolated visual-intent builder missing')
        for path in ['dist','instant-chart-preview','local-library-preview','other-preview']:
            with self.subTest(path=path),self.assertRaises(ValueError):prepare(ROOT/'site/paper-table-audit-preview',ROOT/'site'/path,ROOT/'chart_widget/dist')
    def test_actual_core_library_imports_share_version_and_offline_hash(self):
        from tools.prepare_local_library_preview import prepare_preview
        from tests.site.test_instant_chart_preview import InstantChartTests
        with tempfile.TemporaryDirectory(dir=ROOT/'site',prefix='intent-test-') as d:
            folder=Path(d);build=InstantChartTests().build_fixture(folder);base=ROOT/'site/paper-table-audit-preview'
            report=prepare_preview(base,folder/'one',chart_build=build,visual_policy_version=1);output=folder/'one';core=report['chartCoreDirectory']
            self.assertTrue((output/'assets'/core/'presentation.mjs').is_file())
            for name in ['reader.mjs','contract.mjs']:
                self.assertIn('../'+core+'/',(output/'assets'/report['moduleDirectory']/name).read_text(encoding='utf-8'))
            self.assertEqual(report['visualPresentationVersion'],1)
            manifest=json.loads((output/'library/offline-manifest.json').read_bytes());self.assertTrue(any(core+'/presentation.mjs' in r['url'] for r in manifest['resources']))
            self.assertFalse(any('private' in r['url'] or '/api/' in r['url'] for r in manifest['resources']))
            original=base/'assets/examples/central-tendency-and-dispersion.svg'
            self.assertEqual(original.read_bytes(),(output/'assets/examples'/original.name).read_bytes())
            first=report['runtimeVersion']
            actual_read=Path.read_bytes
            def changed(path):
                raw=actual_read(path)
                return raw+b'\n// intent revision' if path==ROOT/'site/assets/charts/presentation.mjs' else raw
            with patch.object(Path,'read_bytes',changed):second=prepare_preview(base,folder/'two',chart_build=build,visual_policy_version=1)
            self.assertNotEqual(first,second['runtimeVersion'])
