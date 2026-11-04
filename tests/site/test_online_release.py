"""Release integration runs real builders, no provider calls or deployment."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]

class OnlineReleaseTests(unittest.TestCase):
    def test_rebuilding_existing_library_navigation_keeps_one_active_entry(self):
        from tools.prepare_local_library_preview import library_navigation
        html='<nav aria-label="主导航"><a href="../index.html">术语</a><a href="../library/index.html" aria-current="page">我的知识库</a></nav>'
        result=library_navigation(html,'../',active=True)
        self.assertEqual(result.count('>我的知识库</a>'),1)
        self.assertEqual(result.count('aria-current="page"'),1)
        self.assertEqual(library_navigation(result,'../',active=True),result)
    def test_rebuilding_strips_only_obsolete_library_overlays(self):
        from tools.prepare_local_library_preview import strip_library_overlays
        page='<script src="assets/soft-navigation.js"></script><script src="assets/library-runtime.js?v=old" data-library-module="library-old/app-boot.mjs" defer></script><link rel="stylesheet" href="assets/library-old/library.css"><style data-library-entry>old</style>'
        self.assertEqual(strip_library_overlays(page),'<script src="assets/soft-navigation.js"></script>')
    def test_frontend_notice_is_included_in_hashed_release(self):
        prepare=self.api()
        from tests.site.test_instant_chart_preview import InstantChartTests
        with tempfile.TemporaryDirectory(dir=ROOT/'site',prefix='release-test-') as d:
            folder=Path(d);build=InstantChartTests().build_fixture(folder);out=folder/'site/online-release-notices'
            notices=folder/'notices';notices.mkdir();(notices/'LICENSE.txt').write_text('A complete test license')
            with patch('tools.prepare_online_release.ROOT',folder):
                prepare(ROOT/'site/paper-table-audit-preview',out,build,notices_dir=notices)
            manifest=json.loads((out/'release-manifest.json').read_bytes())
            row=next(r for r in manifest['resources'] if r['path']=='assets/third-party/LICENSE.txt')
            self.assertEqual(row['sha256'],hashlib.sha256(b'A complete test license').hexdigest())

    def test_release_rejects_an_oversized_optional_chart_before_publishing(self):
        prepare=self.api()
        with tempfile.TemporaryDirectory(dir=ROOT/'site',prefix='release-test-') as d:
            folder=Path(d);build=folder/'chart-build';build.mkdir();content=b'export function mountChart(){}'+b' '*450001
            (build/'widget.mjs').write_bytes(content);(build/'manifest.json').write_text(json.dumps(dict(version=1,entry='widget.mjs',resources=[dict(file='widget.mjs',sha256=hashlib.sha256(content).hexdigest())])))
            out=folder/'site/online-release-budget'
            with patch('tools.prepare_online_release.ROOT',folder),self.assertRaisesRegex(ValueError,'chart startup budget'):prepare(ROOT/'site/paper-table-audit-preview',out,build)
            self.assertFalse(out.exists())

    def api(self):
        try:from tools.prepare_online_release import prepare_release;return prepare_release
        except ImportError:self.fail('Combined immutable online release builder missing')

    def test_generation_capability_changes_runtime_identity(self):
        from tools.prepare_local_library_preview import prepare_preview
        with tempfile.TemporaryDirectory(dir=ROOT/'site',prefix='release-test-') as d:
            folder=Path(d);base=folder/'base';base.mkdir();(base/'index.html').write_text('<html><head></head><body></body></html>')
            one=prepare_preview(base,folder/'one',online_generation=False)
            two=prepare_preview(base,folder/'two',online_generation=True)
            self.assertNotEqual(one['runtimeVersion'],two['runtimeVersion'],'Soft navigation must not reuse a page with obsolete API capability')

    def test_release_has_online_and_visual_host_without_private_or_qa_paths(self):
        prepare=self.api()
        from tests.site.test_instant_chart_preview import InstantChartTests
        from term_explainer.online.orchestrator import visual_host_for_config
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory(dir=ROOT/'site',prefix='release-test-') as d:
            folder=Path(d);build=InstantChartTests().build_fixture(folder);out=folder/'site/online-release-preview'
            with patch('tools.prepare_online_release.ROOT',folder):report=prepare(ROOT/'site/paper-table-audit-preview',out,build)
            page=(out/'library/index.html').read_text(encoding='utf-8')
            self.assertIn('data-generation-api="api/term-explainer/"',page)
            self.assertEqual(visual_host_for_config(SimpleNamespace(public_root=out,visual_intent_enabled=True)),dict(interactive_chart_types=['bar']))
            self.assertFalse((out/'qa').exists());self.assertFalse((out/'analysis-logs/private').exists())
            manifest=json.loads((out/'release-manifest.json').read_bytes())
            self.assertEqual(manifest['releaseId'],report['releaseId'])
            self.assertTrue(manifest['resources'])
            for item in manifest['resources']:
                self.assertEqual(hashlib.sha256((out/item['path']).read_bytes()).hexdigest(),item['sha256'])
                self.assertFalse(any(p in item['path'].split('/') for p in ['qa','.env','__pycache__','private','fixtures']))
            with self.assertRaises(FileExistsError),patch('tools.prepare_online_release.ROOT',folder):prepare(ROOT/'site/paper-table-audit-preview',out,build)
