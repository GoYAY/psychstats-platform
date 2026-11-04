"""A specifically reviewed scope false positive can reuse a paid response safely."""
from copy import deepcopy
import json
import unittest
from . import test_full_job as fixtures
from term_explainer import full_job as jobs

try:
    from term_explainer.reconciliation import apply_section_scope_review
except ImportError:
    apply_section_scope_review=None


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        f=fixtures.FullJobTests(); f.setUp(); self.addCleanup(f.doCleanups)
        self.f=f; self.payload=f.payload
        state=jobs.create_job(self.payload,None)
        appendix=f.reading(); appendix['anchor_conflicts']=['Appendix describes comparison methods, not the target definition.']
        raw=f.client([f.reading(),appendix])
        proxy=jobs.RecordedClient(raw,state,f.folder/'responses',lambda v:None)
        with self.assertRaises(jobs.JobError): jobs.read_all(state,self.payload,proxy,lambda v:None)
        self.state=state; self.original=deepcopy(state)
        self.event=state['events'][-1]
        self.cache=f.folder/'responses'/(self.event['request_hash']+'.json')
        self.response=json.loads(self.cache.read_text(encoding='utf-8'))
        section=state['reading']['sections'][-1]
        self.review=dict(decision='section_scope_not_anchor_conflict',reviewer='local_source_review',
            reason='This verified section supplies comparative background; it does not replace the user term.',
            source_hash=state['reading']['source_hash'],term_hash=state['reading']['term_hash'],
            section_id=section['id'],request_hash=self.event['request_hash'],response_hash=jobs.fingerprint(self.response),
            dismissed_conflicts=appendix['anchor_conflicts'],
            evidence=[dict(source_id=f.source['id'],start=section['start'],end=section['end'])])

    def apply(self,**kwargs):
        self.assertIsNotNone(apply_section_scope_review,'reviewed cached-response continuation is missing')
        return apply_section_scope_review(self.state,self.payload,kwargs.get('response',self.response),kwargs.get('review',self.review))

    def test_approved_scope_review_preserves_cache_counts_and_completed_readings(self):
        before=self.cache.read_bytes()
        result=self.apply()
        self.assertEqual(result['stage'],'reading')
        self.assertEqual(result['reading']['next_section'],3)
        self.assertEqual(result['reading']['reserved_calls'],2)
        self.assertEqual(result['reading']['confirmed_api_calls'],2)
        self.assertEqual(result['events'],self.original['events'])
        self.assertEqual(result['reading']['readings'][:2],self.original['reading']['readings'])
        self.assertEqual(self.state,self.original)
        self.assertEqual(self.cache.read_bytes(),before)
        self.assertEqual(result['reading']['readings'][-1]['scope_review']['dismissed_conflicts'],self.review['dismissed_conflicts'])
        self.assertFalse(result['reading']['can_generate'])

    def test_mismatched_source_response_or_conflict_cannot_be_dismissed(self):
        for key,value in [('source_hash','0'*64),('response_hash','0'*64),('dismissed_conflicts',['Other conflict']),
                          ('evidence',[dict(source_id='s1',start=0,end=5)])]:
            review=dict(self.review,**{key:value})
            with self.subTest(key=key),self.assertRaises(ValueError): self.apply(review=review)
            self.assertEqual(self.state,self.original)

    def test_identity_mismatch_remains_blocked_even_with_a_scope_review(self):
        response=deepcopy(self.response); data=json.loads(response['reply']['content'])
        data['reading_notes'][0]['identity_check']=dict(status='mismatch',reason='Different DOI.')
        response['reply']['content']=json.dumps(data)
        review=dict(self.review,response_hash=jobs.fingerprint(response))
        with self.assertRaises(ValueError): self.apply(response=response,review=review)

    def test_no_review_is_not_an_implicit_bypass(self):
        with self.assertRaises(ValueError): self.apply(review={})

    def test_already_applied_review_cannot_reserve_or_append_twice(self):
        result=self.apply()
        with self.assertRaises(ValueError): apply_section_scope_review(result,self.payload,self.response,self.review)
        self.assertEqual(result['reading']['next_section'],3)
