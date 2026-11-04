from copy import deepcopy
from unittest.mock import patch
import unittest
from tests.term_explainer.helpers import request_payload,result_payload
from term_explainer.online.config import OnlineError

class QualityTests(unittest.TestCase):
    def test_new_review_policy_binds_question_without_resetting_repair_allowance(self):
        run=self.api();r,l=self.case();saved=[]
        with patch('term_explainer.online.visual_quality.review_visual',return_value=dict(decision='pass',reason='clear',object_paths=['/payload/scenes/0'],refs=[])) as review:
            _,_,state=run(r,l,r['sources'],object(),render=lambda *a:'a',state=None,on_checkpoint=lambda s:saved.append(deepcopy(s)))
            self.assertEqual(state.get('review_policy_version'),4)
            r['question']='另一个具体教学问题。'
            _,_,new=run(r,l,r['sources'],object(),render=lambda *a:'a',state=state,on_checkpoint=lambda s:None)
            self.assertEqual(review.call_count,2);self.assertEqual(new['repairs_used'],state['repairs_used'])

    def test_prior_pass_and_repairs_survive_new_prompt_without_reassessment(self):
        import json
        from pathlib import Path
        run=self.api();r,l=self.case();l['visual']['refs']=[dict(source_id='s1',start=0,end=18)]
        fixture=json.loads((Path(__file__).parents[2]/'fixtures/visual-review-wire-v1.json').read_text(encoding='utf-8'));binding=fixture['fingerprint']
        state=dict(policy_version=1,input_fingerprint=binding,phase='passed',repairs_used=1,reviews={binding+':1':dict(decision='pass',reason='old accepted',object_paths=['/payload/scenes/0'],refs=[])})
        with patch('term_explainer.online.visual_quality.review_visual',side_effect=AssertionError('Do not reassess accepted prior diagrams')):
            _,_,new=run(r,l,r['sources'],object(),render=lambda *a:'assets',state=state,on_checkpoint=lambda s:None)
            self.assertEqual(new['repairs_used'],1);self.assertEqual(new['reviews'],state['reviews'])

    def test_existing_v3_review_state_keeps_policy_and_exhausted_allowance(self):
        from term_explainer.online.visual_quality import fingerprint
        run=self.api();r,l=self.case();binding=fingerprint(r,l,r['sources'])
        state=dict(policy_version=1,review_policy_version=3,input_fingerprint=binding,
                   phase='reviewed',repairs_used=1,reviews={})
        saved=[]
        with patch('term_explainer.online.visual_quality.review_visual',return_value=dict(
                decision='revise',reason='需明确范围。',object_paths=['/payload/scenes/0'],refs=[])) as review,\
                patch('term_explainer.online.visual_quality.repair_visual') as repair:
            with self.assertRaises(OnlineError):
                run(r,l,r['sources'],object(),render=lambda *a:'asset',state=state,
                    on_checkpoint=lambda s:saved.append(deepcopy(s)))
        self.assertEqual(review.call_args.kwargs['policy_version'],3)
        self.assertEqual(saved[-1]['review_policy_version'],3)
        self.assertEqual(saved[-1]['repairs_used'],1)
        repair.assert_not_called()

    def test_changed_question_cannot_reopen_exhausted_v2_repair_allowance(self):
        run=self.api();r,l=self.case();saved=[]
        with patch('term_explainer.online.visual_quality.review_visual',return_value=dict(decision='pass',reason='clear',object_paths=['/payload/scenes/0'],refs=[])):
            _,_,state=run(r,l,r['sources'],object(),render=lambda *a:'a',state=None,on_checkpoint=lambda s:None)
        state['repairs_used']=1;r['question']='从另一个角度理解这一关系。'
        with patch('term_explainer.online.visual_quality.review_visual',return_value=dict(decision='revise',reason='need correction',object_paths=['/payload/scenes/0'],refs=[])) as review,patch('term_explainer.online.visual_quality.repair_visual') as repair:
            with self.assertRaises(OnlineError) as caught:run(r,l,r['sources'],object(),render=lambda *a:'a',state=state,on_checkpoint=lambda s:saved.append(deepcopy(s)))
            self.assertEqual(caught.exception.code,'visual_review_required');review.assert_called_once();repair.assert_not_called()
        self.assertEqual(saved[-1]['repairs_used'],1);self.assertEqual(saved[-1]['phase'],'review_required')

    def test_layout_pending_from_delivery_stays_a_collision_gap(self):
        # delivery.py raises 'visual layout pending: <COLLISION>' once every
        # deterministic layout failed; it must keep collision semantics instead
        # of looking like an unrelated manual stop.
        from term_explainer.online.visual_quality import COLLISION,LAYOUT_PENDING
        run=self.api();r,l=self.case();saved=[]
        def render(*a):raise ValueError(LAYOUT_PENDING+COLLISION)
        with patch('term_explainer.online.visual_quality.repair_visual') as repair:
            with self.assertRaises(OnlineError) as caught:
                run(r,l,r['sources'],object(),render=render,state=None,on_checkpoint=lambda s:saved.append(deepcopy(s)))
        self.assertEqual(caught.exception.code,'visual_review_required');repair.assert_not_called()
        self.assertEqual(saved[-1]['phase'],'review_required');self.assertEqual(saved[-1]['repairs_used'],0)
        self.assertTrue(saved[-1]['stop_reason'].startswith('图示排版问题待处理'))
        self.assertEqual(saved[-1]['pending_issues'][0]['kind'],'collision')

    def api(self):
        try:from term_explainer.online.visual_quality import prepare_visual_delivery;return prepare_visual_delivery
        except ImportError:self.fail('durable visual quality flow missing')
    def case(self):
        r=request_payload();l=result_payload();l['visual']['presentation']=dict(version=1,focus='structure',numeric_role='none',layout='story',interaction='none');return r,l
    def test_mechanical_first_and_pass_is_reused_only_for_same_fingerprint(self):
        run=self.api();r,l=self.case();events=[];saved=[];provider=object()
        def render(v,repaired):events.append('render');return 'assets'
        def review(*a,**kw):events.append('review');return dict(decision='pass',reason='ok',object_paths=['/payload/scenes/0'],refs=[])
        with patch('term_explainer.online.visual_quality.review_visual',side_effect=review) as mock:
            out,assets,state=run(r,l,r['sources'],provider,render=render,state=None,on_checkpoint=lambda s:saved.append(deepcopy(s)))
            self.assertEqual(events,['render','review']);self.assertEqual(state['phase'],'passed');self.assertEqual(l,out)
            run(r,l,r['sources'],provider,render=render,state=state,on_checkpoint=lambda s:None);self.assertEqual(mock.call_count,1)
            r['sources'][0]['text']='改'+r['sources'][0]['text'][1:]
            run(r,l,r['sources'],provider,render=render,state=state,on_checkpoint=lambda s:None);self.assertEqual(mock.call_count,2)
    def test_revise_reserves_once_before_send_and_rechecks_repaired_visual(self):
        run=self.api();r,l=self.case();snapshots=[];revised=deepcopy(l)
        revised['visual']['payload']['scenes'][0]['objects'][0]['state']='selected'
        def repair(*a,**kw):
            self.assertEqual(snapshots[-1]['repairs_used'],1);self.assertEqual(snapshots[-1]['phase'],'repair_reserved');return revised
        with patch('term_explainer.online.visual_quality.review_visual',side_effect=[dict(decision='revise',reason='clarify',object_paths=['/payload/scenes/0'],refs=[]),dict(decision='pass',reason='clear',object_paths=['/payload/scenes/0'],refs=[])]) as review,patch('term_explainer.online.visual_quality.repair_visual',side_effect=repair) as fix:
            out,assets,state=run(r,l,r['sources'],object(),render=lambda *a:'asset',state=None,on_checkpoint=lambda s:snapshots.append(deepcopy(s)))
            self.assertEqual(out,revised);self.assertEqual(fix.call_count,1);self.assertEqual(review.call_count,2);self.assertEqual(state['repairs_used'],1)

    def test_real_review_parsing_and_authorized_title_repair_reach_delivery(self):
        from tests.term_explainer.test_pipeline import ExternalDouble
        run=self.api();r,l=self.case();revised=deepcopy(l)
        revised['visual']['title']='教学示例：'+l['visual']['title']
        provider=ExternalDouble([
            dict(decision='revise',reason='标题标明为教学示例。',object_paths=['/title'],refs=[]),
            dict(decision='pass',reason='示例范围清楚。',object_paths=['/title'],refs=[])])
        snapshots=[]
        with patch('term_explainer.online.visual_quality.repair_visual',return_value=revised) as repair:
            out,_,state=run(r,l,r['sources'],provider,render=lambda *a:'asset',state=None,
                on_checkpoint=lambda s:snapshots.append(deepcopy(s)))
        self.assertEqual(state['phase'],'passed');self.assertEqual(state['repairs_used'],1)
        self.assertEqual(out['blocks'],l['blocks']);self.assertEqual(out['quiz'],l['quiz'])
        self.assertEqual(out['visual']['title'],revised['visual']['title'])
        self.assertEqual(repair.call_args.kwargs['preservation']['authorized'],['/title'])
        self.assertEqual(len(provider.events),2)
    def test_uncertain_and_failed_second_review_never_deliver(self):
        run=self.api();r,l=self.case()
        for decisions in [['uncertain'],['revise','revise']]:
            with self.subTest(decisions=decisions),patch('term_explainer.online.visual_quality.review_visual',side_effect=[dict(decision=d,reason='check',object_paths=['/payload/scenes/0'],refs=[]) for d in decisions]),patch('term_explainer.online.visual_quality.repair_visual',return_value=deepcopy(l)):
                with self.assertRaises(OnlineError) as caught:run(r,l,r['sources'],object(),render=lambda *a:'a',state=None,on_checkpoint=lambda s:None)
                self.assertEqual(caught.exception.code,'visual_review_required')
    def test_exhausted_mechanical_layouts_then_semantic_revision_use_single_allowance(self):
        # The render callback raising COLLISION means every deterministic
        # layout strategy already failed; only then does one model repair run.
        run=self.api();r,l=self.case();events=[]
        def render(v,repaired):
            events.append('render')
            if not repaired:raise ValueError('Figure rendered QA requires correction; artifacts preserved for review')
            return 'asset'
        with patch('term_explainer.online.visual_quality.review_visual',return_value=dict(decision='revise',reason='bad',object_paths=['/payload/scenes/0'],refs=[])) as review,patch('term_explainer.online.visual_quality.repair_visual',return_value=deepcopy(l)) as fix:
            with self.assertRaises(OnlineError):run(r,l,r['sources'],object(),render=render,state=None,on_checkpoint=lambda s:None)
            self.assertEqual(fix.call_count,0);self.assertEqual(review.call_count,0)
    def test_pending_reservation_survives_restart_and_is_not_reset(self):
        run=self.api();r,l=self.case();saved=[]
        with patch('term_explainer.online.visual_quality.review_visual',return_value=dict(decision='revise',reason='bad',object_paths=['/payload/scenes/0'],refs=[])),patch('term_explainer.online.visual_quality.repair_visual',side_effect=RuntimeError('crash')):
            with self.assertRaises(RuntimeError):run(r,l,r['sources'],object(),render=lambda *a:'a',state=None,on_checkpoint=lambda s:saved.append(deepcopy(s)))
        pending=saved[-1];self.assertEqual(pending['phase'],'repair_reserved')
        with patch('term_explainer.online.visual_quality.repair_visual',return_value=deepcopy(l)) as fix,patch('term_explainer.online.visual_quality.review_visual',return_value=dict(decision='pass',reason='ok',object_paths=['/payload/scenes/0'],refs=[])):
            _,_,state=run(r,l,r['sources'],object(),render=lambda *a:'a',state=pending,on_checkpoint=lambda s:None);self.assertEqual(state['repairs_used'],1);self.assertEqual(fix.call_count,1)
    def test_legacy_has_zero_review_and_new_review_needs_persistence(self):
        run=self.api();r,l=self.case()
        with self.assertRaises(OnlineError):run(r,l,r['sources'],None,render=lambda *a:'a',state=None,on_checkpoint=None)
        del l['visual']['presentation']
        with patch('term_explainer.online.visual_quality.review_visual') as review:
            run(r,l,r['sources'],None,render=lambda *a:'a',state=None,on_checkpoint=None);review.assert_not_called()

    def test_exhausted_allowance_keeps_specific_review_for_resume(self):
        run=self.api();r,l=self.case();saved=[]
        review_reason='第二幕把乙先加、甲跟随和名次未变压缩在同一状态，需要增加中间状态。'
        with patch('term_explainer.online.visual_quality.review_visual',return_value=dict(decision='revise',reason=review_reason,object_paths=['/payload/scenes/1'],refs=[])),patch('term_explainer.online.visual_quality.repair_visual',return_value=deepcopy(l)) as fix:
            with self.assertRaises(OnlineError):run(r,l,r['sources'],object(),render=lambda *a:'a',state=None,on_checkpoint=lambda s:saved.append(deepcopy(s)))
        self.assertEqual(fix.call_count,1)
        final=saved[-1]
        self.assertEqual(final['stop_reason'],'single visual revision exhausted')
        pending=final['pending_issues']
        self.assertEqual([p['kind'] for p in pending],['teaching_review'])
        self.assertEqual(pending[0]['reason'],review_reason)
        self.assertEqual(pending[0]['object_paths'],['/payload/scenes/1'])
        self.assertTrue(pending[0].get('visual_fingerprint'))
        self.assertNotIn('single visual revision exhausted',[p.get('reason') for p in pending])

    def test_collision_only_issues_stop_without_model_repair(self):
        run=self.api();r,l=self.case();saved=[]
        collision='Figure rendered QA requires correction; artifacts preserved for review'
        def render(v,repaired):raise ValueError(collision)
        with patch('term_explainer.online.visual_quality.review_visual') as review,patch('term_explainer.online.visual_quality.repair_visual') as fix:
            with self.assertRaises(OnlineError):run(r,l,r['sources'],object(),render=render,state=None,on_checkpoint=lambda s:saved.append(deepcopy(s)))
        review.assert_not_called();fix.assert_not_called()
        final=saved[-1]
        self.assertEqual(final['phase'],'review_required')
        self.assertIn('排版问题待处理',final['stop_reason'])
        self.assertEqual([p['kind'] for p in final['pending_issues']],['collision'])
        self.assertEqual(final['repairs_used'],0)

    def test_rollback_switch_blocks_paid_quality_even_for_resumed_new_story(self):
        from unittest.mock import patch
        from term_explainer.online.delivery import build_delivery
        from term_explainer.online.files import PrivateFiles
        import tempfile
        from pathlib import Path
        r,l=self.case()
        with tempfile.TemporaryDirectory() as d,patch('term_explainer.online.visual_quality.review_visual') as review:
            files=PrivateFiles(Path(d).absolute())
            with self.assertRaises(OnlineError):build_delivery(dict(id='rollback'),r,l,r['sources'],files,external_qa=False,provider=object(),allow_quality_calls=False,on_quality_checkpoint=lambda s:None)
            review.assert_not_called();self.assertFalse(files.path_for('rollback','lesson.zip').exists())
