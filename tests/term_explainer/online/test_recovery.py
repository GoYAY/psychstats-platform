from copy import deepcopy
import json
import unittest
from term_explainer.online.worker import Worker
from term_explainer.pipeline import PipelineError
from .test_api import APIBase


class VisualRecoveryIssueTests(unittest.TestCase):
    def visual_job(self,quality):
        return dict(id='j1',state='waiting_input',progress={'error_code':'visual_review_required'},
            checkpoint=dict(visual_quality=quality,lesson=dict(blocks=[])),manifest={'documents':[]})

    def test_visual_resume_keeps_specific_review_issues(self):
        from term_explainer.online.recovery import reserve_recovery
        from term_explainer.online.visual_quality import visual_fingerprint
        reason='第二幕把过程压缩成状态，需要补回中间状态。'
        visual=dict(kind='story')
        quality=dict(phase='review_required',stop_reason='single visual revision exhausted',
            pending_issues=[dict(kind='teaching_review',reason=reason,object_paths=['/payload/scenes/1'],visual_fingerprint=visual_fingerprint(visual),review_key='k1')],
            revised_lesson=dict(blocks=[],visual=visual),repairs_used=1,reviews={})
        checkpoint=reserve_recovery(self.visual_job(quality))
        q=checkpoint['visual_quality']
        self.assertEqual(q['phase'],'repair_reserved')
        self.assertEqual([i['reason'] for i in q['repair_issues']],[reason])
        self.assertEqual([i['object_paths'] for i in q['repair_issues']],[['/payload/scenes/1']])
        self.assertEqual(q['recovery_history'][-1]['stop_reason'],'single visual revision exhausted')
        self.assertNotIn('single visual revision exhausted',[i.get('reason') for i in q['repair_issues']])

    def test_visual_resume_binds_issues_to_current_visual_only(self):
        from term_explainer.online.recovery import reserve_recovery
        from term_explainer.online.visual_quality import visual_fingerprint
        visual=dict(kind='story')
        quality=dict(phase='review_required',stop_reason='single visual revision exhausted',
            pending_issues=[dict(kind='teaching_review',reason='旧版本意见',visual_fingerprint='a'*64),
                            dict(kind='teaching_review',reason='当前版本缺中间状态',visual_fingerprint=visual_fingerprint(visual))],
            revised_lesson=dict(blocks=[],visual=visual),repairs_used=1,reviews={})
        checkpoint=reserve_recovery(self.visual_job(quality))
        issues=checkpoint['visual_quality']['repair_issues']
        self.assertEqual([i['reason'] for i in issues],['当前版本缺中间状态'])

    def test_visual_resume_without_matching_issues_reports_material_check(self):
        from term_explainer.online.recovery import reserve_recovery
        quality=dict(phase='review_required',stop_reason='single visual revision exhausted',
            pending_issues=[dict(kind='teaching_review',reason='旧版本意见',visual_fingerprint='a'*64)],
            revised_lesson=dict(blocks=[],visual=dict(kind='story')),repairs_used=1,reviews={},
            input_fingerprint='stale')
        job=self.visual_job(quality)
        checkpoint=reserve_recovery(job)
        q=checkpoint['visual_quality']
        self.assertEqual(q['phase'],'blocked_manual_check')
        self.assertEqual(q['issue_binding'],'unmatched')
        self.assertNotIn('repair_issues',q)
        self.assertNotIn('repair_input',q)
        self.assertEqual(checkpoint['recovery_resumes'],0)


class RecoveryTests(APIBase):
    def paused(self, code='invalid_reference_candidate', *, target=True):
        h=self.login();h['Idempotency-Key']='recovery'
        made=self.client.post('jobs',json=self.body(),headers=h).json()
        self.client.post('jobs/'+made['id']+'/start',json={'version':made['version']},headers=h)
        def fail(claim):
            error=PipelineError(code,'PRIVATE_CONTENT')
            if target:
                from term_explainer.online.provider import BudgetedProvider
                from term_explainer.deepseek import ModelReply
                class Reply:
                    def generate(self,messages,*args,**kwargs):return ModelReply('{"invalid":true}','offline',{'total_tokens':0},'stop')
                p=BudgetedProvider(self.config,self.store,self.files,claim,Reply())
                p.generate([dict(role='user',content='Synthetic failed validation response')])
                error.recovery_target=p.last_generation
            raise error
        worker=Worker(self.config,self.store,runner=fail)
        claim=worker.claim(job_id=made['id']);owner=claim['owner_id']
        with self.store.transaction() as db:
            current=self.store._get(db,owner,claim['id'])
            current['checkpoint']={'documents':[],'sentinel':'keep'}
            self.store._write(db,current)
        return worker.execute(claim),h,owner

    def test_validation_failure_pauses_with_safe_recovery_question(self):
        job,h,owner=self.paused()
        self.assertEqual(job['state'],'waiting_input')
        self.assertEqual(job['question']['kind'],'recovery')
        self.assertEqual(job['checkpoint']['sentinel'],'keep')
        self.assertIsNone(job['terminal_at'])
        self.assertNotIn('PRIVATE_CONTENT',json.dumps(job['progress']))

    def test_resume_is_owned_versioned_and_keeps_checkpoint_and_runtime(self):
        job,h,owner=self.paused()
        before=deepcopy(job)
        r=self.client.post('jobs/'+job['id']+'/resume',json={'version':job['version']},headers=h)
        self.assertEqual(r.status_code,202,r.text)
        new=self.store.get_job(owner,job['id'])
        self.assertEqual(new['state'],'queued')
        for key,value in before['checkpoint'].items():self.assertEqual(new['checkpoint'][key],value)
        self.assertEqual(new['checkpoint']['recovery_resumes'],1)
        self.assertEqual(new['active_seconds'],before['active_seconds'])
        again=self.client.post('jobs/'+job['id']+'/resume',json={'version':job['version']},headers=h)
        self.assertEqual(again.status_code,409)

    def test_resume_rejects_missing_csrf_other_owner_and_terminal(self):
        job,h,owner=self.paused();url='jobs/'+job['id']+'/resume'
        self.assertEqual(self.client.post(url,json={'version':job['version']},headers=self.headers).status_code,403)
        from fastapi.testclient import TestClient
        with TestClient(self.app,base_url=self.config.origin+self.config.api_prefix,root_path=self.config.api_prefix.rstrip('/')) as other:
            oh=self.login(other)
            self.assertEqual(other.post(url,json={'version':job['version']},headers=oh).status_code,404)
        end=self.store.transition(owner,job['id'],job['version'],'cancelled',{})
        self.assertEqual(self.client.post(url,json={'version':end['version']},headers=h).status_code,409)

    def test_unknown_receipt_never_becomes_user_resumable(self):
        job,h,owner=self.paused('needs_reconciliation')
        self.assertEqual(job['state'],'needs_reconciliation')
        r=self.client.post('jobs/'+job['id']+'/resume',json={'version':job['version']},headers=h)
        self.assertEqual(r.status_code,409)

    def test_received_usage_is_reported_even_when_failed(self):
        job,h,owner=self.paused('unknown_failure')
        with self.store.transaction() as db:
            db.execute('INSERT INTO provider_calls VALUES(?,?,?,?,?,?,?)',(job['id'],'received-one','generate','received','2026-10-26',25,100))
        dto=self.client.get('jobs/'+job['id']).json()
        self.assertEqual(dto['usage']['confirmed_tokens'],25)
        self.assertEqual(dto['usage']['pending_reserved_tokens'],0)
        self.assertEqual(dto['usage']['calls'],2)

    def test_failure_without_concrete_repair_target_never_offers_noop_resume(self):
        job,h,owner=self.paused(target=False)
        self.assertEqual(job['state'],'failed')

    def test_resume_rejects_missing_receipt(self):
        job,h,owner=self.paused()
        with self.store.transaction() as db:
            db.execute('INSERT INTO provider_calls VALUES(?,?,?,?,?,?,?)',(job['id'],'missing','generate','received','2026-10-26',25,100))
        r=self.client.post('jobs/'+job['id']+'/resume',json={'version':job['version']},headers=h)
        self.assertEqual(r.status_code,409)
        self.assertEqual(self.store.get_job(owner,job['id'])['state'],'waiting_input')
