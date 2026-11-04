import importlib
import json
from pathlib import Path
import sys
import unittest
import tempfile
import hashlib

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'site'))

class InstantChartTests(unittest.TestCase):
    def build_fixture(self,folder):
        build=folder/'chart-build';build.mkdir();content=b'export function mountChart(){}';(build/'widget.mjs').write_bytes(content)
        (build/'manifest.json').write_text(json.dumps(dict(version=1,entry='widget.mjs',resources=[dict(file='widget.mjs',sha256=hashlib.sha256(content).hexdigest())])))
        return build

    def test_build_copies_only_hash_verified_public_assets_into_offline_manifest(self):
        from tools.prepare_local_library_preview import prepare_preview
        with tempfile.TemporaryDirectory(dir=ROOT/'site',prefix='chart-preview-test-') as d:
            folder=Path(d);build=self.build_fixture(folder);base=ROOT/'site/paper-table-audit-preview';output=folder/'candidate'
            report=prepare_preview(base,output,chart_build=build)
            directory=report['chartDirectory'];self.assertRegex(directory,r'^charts-[a-f0-9]{16}$')
            self.assertTrue((output/'assets'/directory/'widget.mjs').is_file())
            manifest=json.loads((output/'library/offline-manifest.json').read_text())
            self.assertTrue(any(directory+'/widget.mjs' in row['url'] for row in manifest['resources']))
            self.assertFalse(any('private/' in row['url'] or '/api/' in row['url'] for row in manifest['resources']))

    def test_bad_hash_or_path_rejected_before_copy_and_original_previews_are_protected(self):
        from tools.prepare_local_library_preview import prepare_preview
        with tempfile.TemporaryDirectory(dir=ROOT/'site',prefix='chart-preview-test-') as d:
            folder=Path(d);build=self.build_fixture(folder)
            for resource in [dict(file='../outside.mjs',sha256='a'*64),dict(file='C:/outside.mjs',sha256='a'*64),dict(file='widget.mjs',sha256='a'*64)]:
                (build/'manifest.json').write_text(json.dumps(dict(version=1,entry=resource['file'],resources=[resource])))
                with self.assertRaises(ValueError):prepare_preview(ROOT/'site/paper-table-audit-preview',folder/'out',chart_build=build)
            with self.assertRaises(ValueError):prepare_preview(ROOT/'site/paper-table-audit-preview',ROOT/'site/online-generation-preview',chart_build=build)

    def test_chart_changes_invalidate_page_runtime_identity(self):
        from tools.prepare_local_library_preview import prepare_preview
        with tempfile.TemporaryDirectory(dir=ROOT/'site',prefix='chart-preview-test-') as d:
            folder=Path(d);build=self.build_fixture(folder);base=folder/'base';base.mkdir();(base/'index.html').write_text('<html><head></head><body></body></html>')
            first=prepare_preview(base,folder/'one',chart_build=build)
            content=b'export function mountChart(){return null}';(build/'widget.mjs').write_bytes(content)
            (build/'manifest.json').write_text(json.dumps(dict(version=1,entry='widget.mjs',resources=[dict(file='widget.mjs',sha256=hashlib.sha256(content).hexdigest())])))
            second=prepare_preview(base,folder/'two',chart_build=build)
            self.assertNotEqual(first['runtimeVersion'],second['runtimeVersion'],'Existing soft-navigation tabs must detect a changed chart runtime')
    def module(self):
        try:return importlib.import_module('sitegen.instant_charts')
        except ModuleNotFoundError:self.fail('Official chart adapter missing')

    def test_bridge_only_change_invalidates_runtime_and_offline_html_hash(self):
        from tools.prepare_instant_chart_preview import integrate_bridge
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            def build(name,bridge,policy=None):
                target=folder/name;(target/'library').mkdir(parents=True);(target/'assets').mkdir()
                for file in (target/'index.html',target/'library/index.html'):file.write_text('<html><head><meta name="psych-runtime" content="old"></head><body></body></html>')
                (target/'library/offline-manifest.json').write_text(json.dumps({'version':'old','resources':[{'url':'index.html','hash':'old'}]}))
                report={'runtimeVersion':'old','chartCoreDirectory':'core','chartDirectory':'charts','chartEntry':'widget.mjs'}
                if policy is not None:report['officialFigurePolicy']=policy
                integrate_bridge(target,report,bridge)
                html=(target/'library/index.html').read_bytes();manifest=json.loads((target/'library/offline-manifest.json').read_text())
                self.assertIn(report['runtimeVersion'].encode(),html);self.assertEqual(manifest['resources'][0]['hash'],hashlib.sha256(html).hexdigest())
                self.assertEqual(json.loads((target/'library-build.json').read_text())['runtimeVersion'],report['runtimeVersion'])
                return report['runtimeVersion']
            self.assertNotEqual(build('one',b'/* first */'),build('two',b'/* repaired */'))
            self.assertNotEqual(build('grouped',b'/* same */','grouped-v1'),build('separate',b'/* same */','preserve-separate-distributions-v1'),'Presentation-only changes must invalidate cached soft-navigation pages')

    def test_annotation_keeps_static_picture_and_only_one_interactive_target(self):
        module=self.module()
        visual={'decision':'draw','kind':'bars','title':'选项人数','chart':{'x_label':'选项','y_label':'人数','series':[{'label':'学生','values':[['甲',2],['乙',3]]}]}}
        original='<main><figure class="plain-example-visual illustrated-example"><h3>题目</h3><picture><img src="old.svg" width="760" height="380"></picture><figcaption>保留正文</figcaption></figure></main>'
        result=module.annotate_official_chart(original,visual,'response-frequency')
        self.assertIn('src="old.svg"',result);self.assertIn('保留正文',result)
        self.assertEqual(result.count('data-instant-chart='),1)
        self.assertIn('data-chart-data',result)
        self.assertIn('甲',result)

    def test_separate_distributions_preserve_original_figure_without_enhancement(self):
        visual=json.loads((ROOT/'site/content/plain_visuals/foundations.json').read_text(encoding='utf-8'))['central-tendency-and-dispersion']
        original='<main><figure class="plain-example-visual illustrated-example"><picture><img src="two-distributions.svg" width="760" height="380"></picture><figcaption>同尺度比较完整分布</figcaption></figure></main>'
        self.assertEqual(self.module().annotate_official_chart(original,visual,'central-tendency-and-dispersion'),original)

    def test_separate_distribution_source_validation_is_not_bypassed(self):
        visual=json.loads((ROOT/'site/content/plain_visuals/foundations.json').read_text(encoding='utf-8'))['central-tendency-and-dispersion']
        visual['chart']['series'][0]['values'][0][1]=1
        original='<figure class="plain-example-visual illustrated-example"><picture><img src="original.svg"></picture></figure>'
        with self.assertRaisesRegex(ValueError,'Original classroom data changed'):
            self.module().annotate_official_chart(original,visual,'central-tendency-and-dispersion')

    def test_invalid_or_ambiguous_figure_aborts_build_instead_of_attaching_elsewhere(self):
        module=self.module();visual={'kind':'bars','decision':'draw','chart':{}}
        with self.assertRaises(ValueError):module.annotate_official_chart('<main>none</main>',visual,'test')
        figure='<figure class="plain-example-visual illustrated-example"><picture></picture></figure>'
        with self.assertRaises(ValueError):module.annotate_official_chart(figure+figure,visual,'test')
