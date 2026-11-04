from copy import deepcopy
from io import BytesIO
import json
import unittest
from unittest.mock import patch
from . import test_budget as budget
from .test_jobs import QueueFixture
from . import test_recovery as recovery
from . import test_visual_quality as quality
from term_explainer.online.provider import BudgetedProvider
from term_explainer.online.visual_quality import fingerprint,prepare_visual_delivery


class TargetedProviderTests(QueueFixture):
    def test_missing_field_repair_cannot_bypass_durable_call_budget(self):
        from term_explainer.pipeline import _analyse
        from term_explainer.contract import validate_request
        from tests.term_explainer.helpers import request_payload
        from tests.term_explainer.test_pipeline import analysis_payload
        from term_explainer.deepseek import ModelReply
        from term_explainer.online.config import OnlineError
        config,store,claim,files,under,p=budget.BudgetTests.setup_provider(self,max_job_calls=1)
        request=request_payload();request['network_allowed']=True;request=validate_request(request)
        incomplete=analysis_payload();del incomplete['reference_candidates']
        def respond(messages,*args,**kwargs):
            under.calls+=1
            return ModelReply(json.dumps(incomplete,ensure_ascii=False),'offline',{'total_tokens':30},'stop')
        under.generate=respond
        with self.assertRaises(OnlineError) as caught:_analyse(request,p,[])
        self.assertEqual(caught.exception.code,'budget_exhausted')
        self.assertEqual(caught.exception.analysis_contract['repair_status'],'not_completed')
        self.assertEqual(under.calls,1)
        self.assertEqual(p.calls,1)

    def test_unknown_repair_response_is_not_blindly_resent(self):
        from term_explainer.pipeline import _analyse
        from term_explainer.contract import validate_request
        from tests.term_explainer.helpers import request_payload
        from tests.term_explainer.test_pipeline import analysis_payload
        from term_explainer.deepseek import ModelReply,DeepSeekError
        from term_explainer.online.config import OnlineError
        config,store,claim,files,under,p=budget.BudgetTests.setup_provider(self)
        request=request_payload();request['network_allowed']=True;request=validate_request(request)
        incomplete=analysis_payload();del incomplete['reference_candidates']
        def respond(messages,*args,**kwargs):
            under.calls+=1
            if under.calls>1:raise DeepSeekError('provider_connection_interrupted','Unknown response')
            return ModelReply(json.dumps(incomplete,ensure_ascii=False),'offline',{'total_tokens':30},'stop')
        under.generate=respond
        with self.assertRaises(DeepSeekError):_analyse(request,p,[])
        resumed=BudgetedProvider(config,store,files,claim,under,clock=lambda:self.now[0])
        with self.assertRaises(OnlineError) as caught:_analyse(request,resumed,[])
        self.assertEqual(caught.exception.code,'needs_reconciliation')
        self.assertEqual(under.calls,2)
        with store.connection() as db:
            self.assertEqual([r['state'] for r in db.execute('SELECT state FROM provider_calls ORDER BY rowid')],['received','sent'])

    def test_worker_persists_host_field_repair_audit_on_failure(self):
        from term_explainer.online.worker import Worker
        from term_explainer.pipeline import PipelineError
        config,store,claim,files,under,p=budget.BudgetTests.setup_provider(self)
        audit=dict(version=1,normalized_fields=[],repair_attempts=1,repaired_fields=['claims'],repair_status='rejected')
        def fail(job):
            error=PipelineError('invalid_evidence_analysis','PRIVATE MODEL CONTENT')
            error.analysis_contract=deepcopy(audit);error.subcode='analysis_repair_incomplete'
            raise error
        result=Worker(config,store,runner=fail,clock=lambda:self.now[0]).execute(claim)
        self.assertEqual(result['checkpoint']['analysis_contract_failure'],audit)
        self.assertEqual(result['progress']['error_subcode'],'analysis_repair_incomplete')
        self.assertNotIn('PRIVATE MODEL CONTENT',json.dumps(result))

    def test_cached_missing_disabled_reference_field_is_revalidated_with_zero_new_calls(self):
        from term_explainer.pipeline import _analyse
        from term_explainer.contract import validate_request
        from tests.term_explainer.helpers import request_payload
        from tests.term_explainer.test_pipeline import analysis_payload,ExternalDouble
        from term_explainer.deepseek import ModelReply
        config,store,claim,files,under,p=budget.BudgetTests.setup_provider(self)
        request=request_payload();request.update(network_allowed=True,max_reference_reads=0)
        request=validate_request(request)
        capture=ExternalDouble([analysis_payload()]);_analyse(request,capture,[])
        incomplete=analysis_payload();del incomplete['reference_candidates']
        def respond(messages,*args,**kwargs):
            under.calls+=1
            return ModelReply(json.dumps(incomplete,ensure_ascii=False),'offline',{'total_tokens':30},'stop')
        under.generate=respond
        p.generate(capture.events[0][1])  # Original received response, before validation.
        key=p.last_generation['key'];receipt=files.path_for(claim['id'],'response-'+key+'.json').read_bytes()
        resumed=BudgetedProvider(config,store,files,claim,under,clock=lambda:self.now[0])
        result=_analyse(request,resumed,[])
        self.assertEqual(result['reference_candidates'],[])
        self.assertEqual(under.calls,1)
        self.assertEqual(store.job_usage(claim['id'],files=files)['confirmed_tokens'],30)
        self.assertEqual(files.path_for(claim['id'],'response-'+key+'.json').read_bytes(),receipt)

    def test_missing_field_repair_receipt_is_cached_and_charged_once_on_restart(self):
        from term_explainer.pipeline import _analyse
        from term_explainer.contract import validate_request
        from tests.term_explainer.helpers import request_payload
        from tests.term_explainer.test_pipeline import analysis_payload
        from term_explainer.deepseek import ModelReply
        config,store,claim,files,under,p=budget.BudgetTests.setup_provider(self)
        request=request_payload();request['network_allowed']=True;request=validate_request(request)
        incomplete=analysis_payload();del incomplete['reference_candidates']
        replies=iter([incomplete,analysis_payload()])
        def respond(messages,*args,**kwargs):
            under.calls+=1
            return ModelReply(json.dumps(next(replies),ensure_ascii=False),'offline',{'total_tokens':30},'stop')
        under.generate=respond
        for _ in range(2):
            resumed=BudgetedProvider(config,store,files,claim,under,clock=lambda:self.now[0])
            self.assertEqual(_analyse(request,resumed,[])['reference_candidates'],[])
        self.assertEqual(under.calls,2)
        self.assertEqual(store.job_usage(claim['id'],files=files)['confirmed_tokens'],60)

    def test_real_compilation_repairs_only_failed_cached_step(self):
        from term_explainer.pipeline import prepare_evidence,generate_prepared_lesson,PipelineError
        from term_explainer.contract import validate_request
        from tests.term_explainer.test_pipeline import analysis_payload
        from tests.term_explainer.helpers import request_payload,result_payload
        from term_explainer.deepseek import ModelReply
        config,store,claim,files,under,p=budget.BudgetTests.setup_provider(self)
        replies=iter([analysis_payload(),{}, {},result_payload()])
        def respond(messages,*args,**kwargs):
            under.calls+=1
            return ModelReply(json.dumps(next(replies),ensure_ascii=False),'offline',{'total_tokens':30},'stop')
        under.generate=respond;r=validate_request(request_payload())
        prepared=prepare_evidence(r,p)
        with self.assertRaises(PipelineError) as caught:generate_prepared_lesson(r,p,prepared)
        self.assertEqual(caught.exception.code,'invalid_lesson')
        target=p.last_generation
        current=deepcopy(claim);current['checkpoint']={'recovery_requests':{target['base_key']:dict(attempt=1,prior_key=target['key'],code='invalid_lesson')}}
        resumed=BudgetedProvider(config,store,files,current,under,clock=lambda:self.now[0])
        reused=prepare_evidence(r,resumed)
        result=generate_prepared_lesson(r,resumed,reused)
        self.assertEqual(result.action,'complete')
        self.assertEqual(under.calls,4)  # reading + two invalid replies + one targeted correction

    def test_only_failed_step_gets_new_request_and_restart_reuses_it(self):
        config,store,claim,files,under,p=budget.BudgetTests.setup_provider(self)
        a=[dict(role='user',content='accepted reading')]
        b=[dict(role='user',content='invalid compilation')]
        p.generate(a);p.generate(b)
        target=p.last_generation
        updated=deepcopy(claim)
        updated['checkpoint']={'recovery_requests':{target['base_key']:dict(attempt=1,prior_key=target['key'],code='invalid_lesson')}}
        resumed=BudgetedProvider(config,store,files,updated,under,clock=lambda:self.now[0])
        resumed.generate(a);resumed.generate(b)
        self.assertEqual(under.calls,3)
        restarted=BudgetedProvider(config,store,files,updated,under,clock=lambda:self.now[0])
        restarted.generate(a);restarted.generate(b)
        self.assertEqual(under.calls,3)
        self.assertEqual(store.job_usage(claim['id'],files=files)['confirmed_tokens'],90)

    def test_failed_known_usage_requires_receipt_proof(self):
        config,store,claim,files,under,p=budget.BudgetTests.setup_provider(self)
        for key,usage in [('actual',{'total_tokens':25}),('unknown',{})]:
            files.put(claim['id'],'response-'+key+'.json',BytesIO(json.dumps({'_known_error':'model_truncated','usage':usage}).encode()),config.limits)
            with store.transaction() as db:
                db.execute('INSERT INTO provider_calls VALUES(?,?,?,?,?,?,?)',(claim['id'],key,'generate','failed_known','2026-10-26',25 if key=='actual' else 100,20))
        u=store.job_usage(claim['id'],files=files)
        self.assertEqual(u['confirmed_tokens'],25)
        self.assertEqual(u['pending_reserved_tokens'],100)
        self.assertEqual(u['unconfirmed_calls'],1)


class ActualResumeTests(recovery.APIBase):
    paused=recovery.RecoveryTests.paused
    def test_invalid_lesson_has_recovery_path(self):
        job,h,owner=self.paused('invalid_lesson')
        self.assertEqual(job['state'],'waiting_input')

    def test_visual_resume_reserves_new_repair_without_erasing_history(self):
        job,h,owner=self.paused('visual_review_required')
        self.assertEqual(job['state'],'waiting_input')
        r,l=quality.QualityTests().case()
        state=dict(policy_version=1,review_policy_version=3,input_fingerprint=fingerprint(r,l,r['sources']),phase='review_required',repairs_used=1,reviews={'old':{}},failure='off topic')
        with self.store.transaction() as db:
            current=self.store._get(db,owner,job['id'])
            current['checkpoint']['visual_quality']=state
            self.store._write(db,current)
        result=self.client.post('jobs/'+job['id']+'/resume',json={'version':job['version']},headers=h)
        self.assertEqual(result.status_code,202,result.text)
        updated=self.store.get_job(owner,job['id'])['checkpoint']['visual_quality']
        with patch('term_explainer.online.visual_quality.repair_visual',return_value=l) as repair,patch('term_explainer.online.visual_quality.review_visual',return_value=dict(decision='pass',reason='ok',object_paths=['/payload/scenes/0'],refs=[])):
            _,_,done=prepare_visual_delivery(r,l,r['sources'],object(),render=lambda *a:'asset',state=updated,on_checkpoint=lambda s:None)
        repair.assert_called_once()
        self.assertEqual(done['phase'],'passed')
        self.assertEqual(done['repairs_used'],1)
        self.assertIn('old',done['reviews'])

