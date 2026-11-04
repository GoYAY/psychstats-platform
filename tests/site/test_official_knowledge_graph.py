import importlib
import json
from pathlib import Path
import tempfile
import unittest

class OfficialGraphTest(unittest.TestCase):
    def test_all_ten_official_topics_cover_every_published_term_exactly_once(self):
        root=Path(__file__).resolve().parents[2]
        graph=self.builder()(root/'site/paper-table-audit-preview',root/'site/content/registry.json')
        expected=['foundations','hypothesis-testing','group-comparisons','regression','data-preparation','classification-clustering','factor-analysis','structural-equation-modeling','mediation-moderation','multilevel-longitudinal']
        self.assertEqual([f['id'] for f in graph['frameworks']],expected)
        assigned=[t for f in graph['frameworks'] for t in f['core']]
        self.assertEqual(len(assigned),len(set(assigned)))
        self.assertEqual(set(assigned),{t['id'] for t in graph['terms']})
        edges={e['key']:e for e in graph['edges']}
        for frame in graph['frameworks']:
            self.assertTrue(frame['core'],frame['id'])
            self.assertTrue(frame['edgeKeys'],frame['id'])
            members=set(frame['core']+frame['oneHop'])
            for key in frame['edgeKeys']:
                self.assertTrue({edges[key]['from']['id'],edges[key]['to']['id']}<=members)
                self.assertTrue(edges[key]['sourceRecords'])
    def test_public_definition_extracts_section_body_not_heading_or_next_section(self):
        api=importlib.import_module('tools.official_knowledge_graph')
        self.assertTrue(callable(getattr(api,'published_definition',None)))
        html='<section><h2>操作性定义</h2><p>样本是<strong>实际观察</strong>的对象。</p></section><section><h2>通俗解释</h2><p>不应混入。</p></section>'
        self.assertEqual(api.published_definition(html),'样本是实际观察的对象。')
    def builder(self):
        try:return importlib.import_module('tools.official_knowledge_graph').official_graph
        except ModuleNotFoundError:self.fail('Official graph extractor missing')
    def test_published_sidebar_only_preserves_types_and_sources(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'terms').mkdir();(p/'assets/data').mkdir(parents=True)
            terms=[{'id':'a','zh':'甲','topic':'factor-analysis'},{'id':'b','zh':'乙','topic':'multilevel-longitudinal'}]
            (p/'assets/data/search-index.json').write_text(json.dumps(terms),encoding='utf-8')
            (p/'registry.json').write_text(json.dumps({'terms':terms}),encoding='utf-8')
            (p/'terms/a.html').write_text('<a href="bad.html">正文</a><aside class="knowledge-sidebar"><section data-relation="contrasts"><a href="b.html">乙</a></section><section data-relation="next"><a href="b.html">乙</a><a href="missing.html">缺页</a></section></aside>',encoding='utf-8')
            (p/'terms/b.html').write_text('<aside class="knowledge-sidebar"><section data-relation="contrasts"><a href="a.html">甲</a></section></aside>',encoding='utf-8')
            result=self.builder()(p,p/'registry.json')
            self.assertEqual(len(result['edges']),2)
            comparison=next(e for e in result['edges'] if e['type']=='contrasts')
            self.assertEqual(len(comparison['sourceRecords']),2)
            self.assertEqual({e['type'] for e in result['edges']},{'contrasts','next'})
            self.assertTrue(any(w['code']=='MISSING_PUBLISHED_TARGET' for w in result['warnings']))
            self.assertEqual(len(result['sourceHashes']),2)
    def test_real_framework_core_counts_and_private_boundary(self):
        root=Path(__file__).resolve().parents[2]
        result=self.builder()(root/'site/paper-table-audit-preview',root/'site/content/registry.json')
        frames={f['id']:f for f in result['frameworks']}
        self.assertEqual(len(frames['factor-analysis']['core']),26)
        self.assertEqual(len(frames['multilevel-longitudinal']['core']),14)
        self.assertEqual(frames['multilevel-longitudinal']['edgeCounts']['components'],11)
        self.assertEqual(len({t['id'] for t in result['terms']}),179)
        raw=json.dumps(result,ensure_ascii=False)
        for private in ['cognitive-drift','human-ai-entanglement','dominant-trait-profile','span_id','.pdf']:self.assertNotIn(private,raw)
