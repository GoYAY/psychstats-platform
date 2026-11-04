from copy import deepcopy
import unittest
from tests.term_explainer.helpers import request_payload,result_payload
from tests.term_explainer.test_pipeline import ExternalDouble
import json
from pathlib import Path

class VisualReviewTests(unittest.TestCase):
    def test_new_review_sends_user_question_and_legal_object_catalogue(self):
        api=self.api();r,l=self.case();client=ExternalDouble([dict(decision='pass',reason='对象清楚。',object_paths=['/payload/scenes/0/objects/0'],refs=l['visual']['refs'])])
        api.review_visual(r,l,r['sources'],client)
        context=json.loads(client.events[0][1][1]['content'])
        self.assertEqual(context.get('question'),r['question'])
        targets={t['path']:t['kind'] for t in context.get('review_targets',[])}
        self.assertEqual(targets.get('/payload/scenes/0/objects/0'),'object')
        self.assertEqual(targets.get('/payload/scenes/0/objects'),'collection')
        self.assertNotIn('/payload/scenes/0/objects/0/label',targets)
        self.assertNotIn('/refs',targets)

    def test_explicit_legacy_review_preserves_wire_request_exactly(self):
        api=self.api();r,l=self.case();fixture=json.loads((Path(__file__).parents[2]/'fixtures/visual-review-wire-v1.json').read_text(encoding='utf-8'))
        c=ExternalDouble([dict(decision='pass',reason='对象清楚。',object_paths=['/payload/scenes/0/objects/0'],refs=l['visual']['refs'])])
        api.review_visual(r,l,r['sources'],c,policy_version=1)
        self.assertEqual(c.events[0][1],fixture['messages'],'Saved v1 receipts must keep the exact request hash')

    def api(self):
        try:from term_explainer.online import visual_review;return visual_review
        except ImportError:self.fail('minimal-evidence visual review missing')

    def test_catalogue_escapes_keys_and_excludes_scalar_ids(self):
        api=self.api()
        visual=dict(payload={'a/b':{'~items':[{'id':'x'},'x']}})
        targets=api.review_targets(visual)
        self.assertEqual(targets,[dict(path='/payload/a~1b',kind='object'),dict(path='/payload/a~1b/~0items',kind='collection'),dict(path='/payload/a~1b/~0items/0',kind='object')])
        context=dict(visual=visual,evidence=[],review_targets=targets)
        good=dict(decision='pass',reason='可指认。',object_paths=['/payload/a~1b/~0items/0'],refs=[])
        self.assertEqual(api.validate_review(good,context,[]),good)
        for path in ['/payload/a~1b/~0items/1','/payload/a~1b/~0items/0/id','/payload/unknown']:
            with self.subTest(path=path),self.assertRaises(ValueError):api.validate_review(dict(good,object_paths=[path]),context,[])

    def test_review_version_is_host_integer_only(self):
        api=self.api();r,l=self.case()
        for version in [True,0,5,'2']:
            client=ExternalDouble([])
            with self.subTest(version=version),self.assertRaises(ValueError):api.review_visual(r,l,r['sources'],client,policy_version=version)
            self.assertEqual(client.events,[])

    def test_v4_catalogue_exposes_exact_wording_targets_and_accepts_title_review(self):
        api=self.api();r,l=self.case()
        for field in ('title','takeaway','alt'):
            answer=dict(decision='revise',reason='将数字限定为教学示例。',object_paths=['/'+field],refs=l['visual']['refs'])
            c=ExternalDouble([answer])
            with self.subTest(field=field):
                self.assertEqual(api.review_visual(r,l,r['sources'],c,policy_version=4),answer)
                context=json.loads(c.events[0][1][1]['content'])
                targets={t['path']:t['kind'] for t in context['review_targets']}
                self.assertEqual(targets['/'+field],'wording')
                for denied in ('/refs','/kind','/origin','/presentation'):
                    self.assertNotIn(denied,targets)

    def test_v4_wording_support_does_not_relax_legacy_or_arbitrary_scalar_paths(self):
        api=self.api();r,l=self.case()
        for version,path in [(3,'/title'),(4,'/refs'),(4,'/origin'),
                             (4,'/title/anything'),(4,'/payload/scenes/0/objects/0/label')]:
            answer=dict(decision='revise',reason='修改。',object_paths=[path],refs=[])
            with self.subTest(version=version,path=path),self.assertRaises(ValueError):
                api.review_visual(r,l,r['sources'],ExternalDouble([answer]),policy_version=version)

    def case(self):
        request=request_payload();lesson=result_payload();lesson['visual']['refs']=[dict(source_id='s1',start=0,end=18)]
        lesson['visual']['presentation']=dict(version=1,focus='structure',numeric_role='none',layout='story',interaction='none')
        return request,lesson

    def test_review_routes_all_new_teaching_figures_and_preserves_legacy(self):
        api=self.api();request,lesson=self.case();v=lesson['visual'];self.assertTrue(api.requires_visual_review(v))
        del v['presentation'];self.assertFalse(api.requires_visual_review(v))
        v.update(kind='statistical',payload=dict(chart_type='bar',series=[dict(label='甲',x=[1],y=[2]),dict(label='乙',x=[1],y=[3])]),presentation=dict(version=1,focus='whole',numeric_role='relative',layout='grouped',interaction='none'));self.assertTrue(api.requires_visual_review(v))
        v['presentation']['focus']='local';self.assertTrue(api.requires_visual_review(v))
        v['presentation']['layout']='facets';self.assertTrue(api.requires_visual_review(v))

    def test_minimal_context_has_complete_deduplicated_snippet_not_entire_sources(self):
        api=self.api();r,l=self.case();r['sources'][0]['text']+='UNRELATED PRIVATE FULL BODY';l['visual']['refs']*=2;l['provenance']={'private':'secret'}
        before=deepcopy(l);c=api.build_review_context(r,l,r['sources'])
        self.assertEqual(c['evidence'],[dict(source_id='s1',start=0,end=18,text=r['sources'][0]['text'][:18])]);self.assertEqual(l,before)
        self.assertNotIn('UNRELATED PRIVATE',str(c));self.assertNotIn('secret',str(c));self.assertNotIn('sources',c)

    def test_protocol_checks_real_objects_and_original_refs(self):
        api=self.api();r,l=self.case();good=dict(decision='pass',reason='对象与范围一致。',object_paths=['/payload/scenes/0/objects/0'],refs=l['visual']['refs'])
        client=ExternalDouble([good]);self.assertEqual(api.review_visual(r,l,r['sources'],client),good);self.assertEqual(len(client.events),1)
        for change in [dict(decision='invented'),dict(reason=''),dict(object_paths=['/payload/nonexistent']),dict(object_paths=['/payload/scenes/0/objects/0/label']),dict(refs=[dict(source_id='s1',start=18,end=22)]),dict(code='print(1)'),dict(reason='https://evil.invalid'),dict(object_paths=[])]:
            with self.subTest(change=change),self.assertRaises(ValueError):api.review_visual(r,l,r['sources'],ExternalDouble([dict(good,**change)]))
        good.update(decision='uncertain',object_paths=[]);self.assertEqual(api.review_visual(r,l,r['sources'],ExternalDouble([good]))['decision'],'uncertain')
