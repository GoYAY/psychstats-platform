from dataclasses import replace
from term_explainer.online.provider import BudgetedProvider
from term_explainer.online.files import PrivateFiles
from term_explainer.online.worker import Worker
from term_explainer.online.config import OnlineError
from term_explainer.deepseek import ModelReply,DeepSeekError
from .test_jobs import QueueFixture

class Provider:
    def __init__(self):self.calls=0;self.fail=False
    def generate(self,messages,*args,**kwargs):
        self.calls+=1
        if self.fail:raise DeepSeekError('provider_timeout','timeout')
        return ModelReply('{"ok":true}','deepseek-flash',{'total_tokens':30},'stop')

class BudgetTests(QueueFixture):
    def test_v1_pending_review_reuses_preupgrade_receipt_without_resetting_repairs(self):
        import json
        from pathlib import Path
        from tests.term_explainer.online.test_visual_review import VisualReviewTests
        from term_explainer.online.visual_quality import prepare_visual_delivery
        config,store,claim,files,under,p=self.setup_provider();request,lesson=VisualReviewTests().case()
        fixture=json.loads((Path(__file__).parents[2]/'fixtures/visual-review-wire-v1.json').read_text(encoding='utf-8'))
        def respond(messages,*args,**kwargs):
            under.calls+=1;return ModelReply(json.dumps(dict(decision='pass',reason='对象清楚',object_paths=['/payload/scenes/0/objects/0'],refs=lesson['visual']['refs'])),'deepseek-flash',dict(total_tokens=30),'stop')
        under.generate=respond;p.generate(fixture['messages']);binding=fixture['fingerprint']
        state=dict(policy_version=1,input_fingerprint=binding,phase='review_reserved',repairs_used=1,reviews={})
        _,_,state=prepare_visual_delivery(request,lesson,request['sources'],p,render=lambda *a:'asset',state=state,on_checkpoint=lambda s:None)
        self.assertEqual(state['phase'],'passed');self.assertEqual(state['repairs_used'],1);self.assertEqual(under.calls,1)

    def test_quality_recovery_reuses_receipt_after_checkpoint_crash(self):
        from copy import deepcopy
        import json
        from .visual_dummy import quality_case
        from term_explainer.online.visual_quality import prepare_visual_delivery
        config,store,claim,files,under,p=self.setup_provider();request,lesson=quality_case();saved=[]
        def respond(messages,*args,**kwargs):
            under.calls+=1;return ModelReply(json.dumps(dict(decision='pass',reason='对象范围清楚',object_paths=['/payload/scenes/0'],refs=[])),'deepseek-flash',dict(total_tokens=30),'stop')
        under.generate=respond
        def checkpoint(s):
            if s['phase']=='reviewed':raise RuntimeError('checkpoint interrupted after provider receipt')
            saved.append(deepcopy(s))
        with self.assertRaises(RuntimeError):prepare_visual_delivery(request,lesson,request['sources'],p,render=lambda *a:'asset',state=None,on_checkpoint=checkpoint)
        self.assertEqual(saved[-1]['phase'],'review_reserved')
        _,_,state=prepare_visual_delivery(request,lesson,request['sources'],p,render=lambda *a:'asset',state=saved[-1],on_checkpoint=lambda s:None)
        self.assertEqual(state['phase'],'passed');self.assertEqual(under.calls,1)

    def test_wire_complete_receipt_is_cached_accounted_once_and_framing_warning_retained(self):
        import json
        from tests.term_explainer.http_response_fixture import response_server
        from tests.term_explainer.test_deepseek_wire import complete_envelope,local_client
        config,store,claim,files,under,p=self.setup_provider()
        with response_server(json.dumps(complete_envelope()).encode(),heartbeats=True) as (url,requests):
            p=BudgetedProvider(config,store,files,claim,local_client(url),clock=lambda:self.now[0])
            for _ in range(2):self.assertEqual(p.generate([{'role':'user','content':'JSON'}]).content,'{"ok":true}')
            self.assertEqual(len(requests),1)
        with store.connection() as db:
            row=db.execute('SELECT * FROM provider_calls').fetchone()
            self.assertEqual(row['state'],'received');self.assertEqual(row['reserved_tokens'],20)
            diagnostic=json.loads(files.path_for(claim['id'],'transport-'+row['key']+'.json').read_bytes())
            self.assertEqual(diagnostic['basis'],'complete_json_completion_and_usage')
            self.assertFalse(files.path_for(claim['id'],'partial-'+row['key']+'.bin').exists())

    def test_partial_http_body_preserves_unknown_reservation_and_never_resends(self):
        from http.client import IncompleteRead
        from unittest.mock import patch
        from term_explainer.deepseek import DeepSeekClient
        config,store,claim,files,under,p=self.setup_provider()
        with patch('term_explainer.deepseek.build_opener') as opener:
            opener.return_value.open.return_value.__enter__.return_value.read.side_effect=IncompleteRead(b'private',999)
            raw=DeepSeekClient(api_key='offline',max_calls=2)
            p=BudgetedProvider(config,store,files,claim,raw,clock=lambda:self.now[0])
            with self.assertRaises(DeepSeekError) as caught:p.generate([{'role':'user','content':'JSON'}])
            self.assertEqual(caught.exception.code,'provider_connection_interrupted')
            with self.assertRaises(OnlineError) as caught:p.generate([{'role':'user','content':'JSON'}])
            self.assertEqual(caught.exception.code,'needs_reconciliation')
            self.assertEqual(opener.return_value.open.call_count,1)
        with store.connection() as db:
            row=db.execute('SELECT * FROM provider_calls').fetchone()
            self.assertEqual(row['state'],'sent');self.assertGreater(row['reserved_tokens'],0)
            diagnostic=files.path_for(claim['id'],'transport-'+row['key']+'.json')
            import json
            self.assertEqual(json.loads(diagnostic.read_bytes())['kind'],'IncompleteRead')
            self.assertEqual(files.path_for(claim['id'],'partial-'+row['key']+'.bin').read_bytes(),b'private')
            self.assertFalse(files.path_for(claim['id'],'response-'+row['key']+'.json').exists())

    def test_received_truncated_response_retains_receipt_and_actual_usage_without_reissue(self):
        from term_explainer.deepseek import DeepSeekClient
        import json
        config,store,claim,files,under,p=self.setup_provider();sent=[]
        def transport(url,payload,headers,timeout):
            sent.append(payload)
            return {'model':'deepseek-flash','usage':{'prompt_tokens':20,'completion_tokens':22,'total_tokens':42},'choices':[{'finish_reason':'length','message':{'content':'partial'}}]}
        raw=DeepSeekClient(api_key='offline',max_calls=2,transport=transport)
        p=BudgetedProvider(config,store,files,claim,raw,clock=lambda:self.now[0])
        for _ in range(2):
            with self.assertRaises(DeepSeekError) as c:p.generate([{'role':'user','content':'test'}])
            self.assertEqual(c.exception.code,'model_truncated')
        with store.connection() as db:
            row=db.execute('SELECT * FROM provider_calls').fetchone()
            self.assertEqual(row['state'],'failed_known')
            self.assertEqual(row['reserved_tokens'],42)
            self.assertGreater(row['output_bytes'],0)
        self.assertEqual(len(sent),1)

    def test_known_http_access_error_is_cached_without_reissuing_request(self):
        config,store,claim,files,under,p=self.setup_provider()
        def denied(messages,*args,**kwargs):
            under.calls+=1;raise DeepSeekError('provider_http_403','source blocked')
        under.generate=denied
        for _ in range(2):
            with self.assertRaises(DeepSeekError) as c:p.generate([{'role':'user','content':'test'}])
            self.assertEqual(c.exception.code,'provider_http_403')
        self.assertEqual(under.calls,1)

    def test_transient_http_status_releases_reservation_and_is_retried(self):
        from unittest.mock import patch
        config,store,claim,files,under,p=self.setup_provider();attempts=[]
        def flaky(messages,*args,**kwargs):
            under.calls+=1;attempts.append(1)
            if len(attempts)<3:raise DeepSeekError('provider_http_503','provider overloaded')
            return ModelReply('{"ok":true}','deepseek-flash',{'total_tokens':30},'stop')
        under.generate=flaky
        with patch('term_explainer.online.provider.TRANSPORT_RETRY_DELAYS',(0,0)):
            self.assertEqual(p.generate([{'role':'user','content':'JSON'}]).content,'{"ok":true}')
        self.assertEqual(under.calls,3)
        with store.connection() as db:
            rows=db.execute('SELECT state,reserved_tokens FROM provider_calls').fetchall()
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['state'],'received');self.assertEqual(rows[0]['reserved_tokens'],30)

    def test_exhausted_transient_retries_leave_no_stalled_reservation(self):
        from unittest.mock import patch
        config,store,claim,files,under,p=self.setup_provider()
        def down(messages,*args,**kwargs):
            under.calls+=1;raise DeepSeekError('provider_http_503','provider overloaded')
        under.generate=down
        with patch('term_explainer.online.provider.TRANSPORT_RETRY_DELAYS',(0,0)):
            with self.assertRaises(DeepSeekError) as caught:p.generate([{'role':'user','content':'JSON'}])
        self.assertEqual(caught.exception.code,'provider_http_503');self.assertEqual(under.calls,3)
        with store.connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM provider_calls').fetchone()[0],0)

    def test_setup_provider_helper_keeps_fresh_key_clear(self):
        config,store,claim,files,under,p=self.setup_provider()
        p.generate([{'role':'user','content':'JSON'}])
        self.assertIsNone(p._fresh_key)

    def test_recovery_continuation_sends_a_flat_message_list(self):
        from copy import deepcopy
        import json
        config,store,claim,files,under,p=self.setup_provider();sent=[]
        def respond(messages,*args,**kwargs):
            under.calls+=1;sent.append(messages)
            return ModelReply('{"ok":true}','deepseek-flash',{'total_tokens':30},'stop')
        under.generate=respond
        p.generate([dict(role='user',content='first')])
        target=p.last_generation
        updated=deepcopy(claim)
        updated['checkpoint']={'recovery_requests':{target['base_key']:dict(attempt=1,prior_key=target['key'],code='invalid_lesson')}}
        BudgetedProvider(config,store,files,updated,under,clock=lambda:self.now[0]).generate([dict(role='user',content='first')])
        self.assertTrue(all(isinstance(m,dict) for m in sent[-1]))
        self.assertEqual([m['role'] for m in sent[-1]],['user','assistant','user'])

    def test_analysis_failure_names_the_check_that_rejected_the_output(self):
        from term_explainer.online.diagnostics import describe_failure
        from term_explainer.pipeline import PipelineError
        error=PipelineError('invalid_evidence_analysis','已保留')
        error.subcode='analysis_multiple_sources_require_explicit_per_paper_contributions'
        self.assertEqual(describe_failure(error)[1]['error_subcode'],error.subcode)
        error.subcode='analysis_/etc/passwd model text'
        self.assertNotIn('error_subcode',describe_failure(error)[1])

    def test_malformed_messages_are_refused_before_spending_a_call(self):
        config,store,claim,files,under,p=self.setup_provider()
        with self.assertRaises(OnlineError) as caught:p.generate([[dict(role='user',content='x')]])
        self.assertEqual(caught.exception.code,'invalid_wire_request');self.assertEqual(under.calls,0)

    def test_rejected_request_keeps_the_vendor_explanation(self):
        import io
        from unittest.mock import patch
        from urllib.error import HTTPError
        from term_explainer.deepseek import DeepSeekClient
        config,store,claim,files,under,p=self.setup_provider()
        with patch('term_explainer.deepseek.build_opener') as opener:
            opener.return_value.open.side_effect=HTTPError('https://api.deepseek.com',422,'Unprocessable Entity',{},io.BytesIO(b'{"error":"bad max_tokens"}'))
            p=BudgetedProvider(config,store,files,claim,DeepSeekClient(api_key='offline',max_calls=2),clock=lambda:self.now[0])
            with self.assertRaises(DeepSeekError) as caught:p.generate([{'role':'user','content':'JSON'}])
        self.assertEqual(caught.exception.code,'provider_http_422')
        with store.connection() as db:key=db.execute('SELECT key FROM provider_calls').fetchone()[0]
        self.assertIn('bad max_tokens',files.path_for(claim['id'],'provider-error-'+key+'.txt').read_text(encoding='utf-8'))

    def setup_provider(self,**changes):
        config,store,owner,job=self.queue()
        if changes:config=replace(config,limits=replace(config.limits,**changes))
        claim=Worker(config,store,runner=lambda j:None,clock=lambda:self.now[0]).claim()
        files=PrivateFiles(config.private_root/'tasks');under=Provider()
        return config,store,claim,files,under,BudgetedProvider(config,store,files,claim,under,clock=lambda:self.now[0])

    def test_saved_response_replays_after_restart_with_zero_new_calls(self):
        config,store,claim,files,under,p=self.setup_provider()
        messages=[{'role':'user','content':'test'}];first=p.generate(messages)
        second=BudgetedProvider(config,store,files,claim,under,clock=lambda:self.now[0]).generate(messages)
        self.assertEqual(first,second);self.assertEqual(under.calls,1)

    def test_budget_exhausted_before_send_and_cancellation_stops_calls(self):
        config,store,claim,files,under,p=self.setup_provider(max_job_calls=1)
        p.generate([{'role':'user','content':'one'}])
        with self.assertRaises(OnlineError) as c:p.generate([{'role':'user','content':'two'}])
        self.assertEqual(c.exception.code,'budget_exhausted');self.assertEqual(under.calls,1)
        fresh=store.get_job(claim['owner_id'],claim['id']);store.transition(fresh['owner_id'],fresh['id'],fresh['version'],'cancelled',{})
        with self.assertRaises(OnlineError):p.generate([{'role':'user','content':'one'}])
        self.assertEqual(under.calls,1)

    def test_uncertain_request_is_not_reissued_and_reservation_is_not_released(self):
        config,store,claim,files,under,p=self.setup_provider();under.fail=True
        messages=[{'role':'user','content':'private content'}]
        with self.assertRaises(DeepSeekError):p.generate(messages)
        under.fail=False
        with self.assertRaises(OnlineError) as c:p.generate(messages)
        self.assertEqual(c.exception.code,'needs_reconciliation');self.assertEqual(under.calls,1)
        with store.connection() as db:
            row=db.execute('SELECT state,reserved_tokens FROM provider_calls').fetchone()
            self.assertEqual(row['state'],'sent');self.assertGreater(row['reserved_tokens'],0)

    def test_daily_budget_shared_across_owners(self):
        config,store,claim,files,under,p=self.setup_provider(max_daily_calls=1)
        p.generate([{'role':'user','content':'one'}])
        from term_explainer.online.auth import InviteAuth
        fresh=store.get_job(claim['owner_id'],claim['id']);store.transition(fresh['owner_id'],fresh['id'],fresh['version'],'cancelled',{})
        auth=InviteAuth(store,config,clock=lambda:self.now[0]);owner=auth.exchange(auth.create_invite('other')).owner_id
        job=store.create_job(owner,'other',{'kind':'lesson'});store.transition(owner,job['id'],job['version'],'queued',{})
        other=Worker(config,store,runner=lambda j:None,clock=lambda:self.now[0]).claim()
        q=BudgetedProvider(config,store,files,other,under,clock=lambda:self.now[0])
        with self.assertRaises(OnlineError):q.generate([{'role':'user','content':'two'}])
        self.assertEqual(under.calls,1)

    def test_runtime_limit_applies_before_any_send(self):
        config,store,claim,files,under,p=self.setup_provider(max_task_seconds=1)
        self.now[0]+=2
        with self.assertRaises(OnlineError) as c:p.generate([{'role':'user','content':'one'}])
        self.assertEqual(c.exception.code,'task_timeout');self.assertEqual(under.calls,0)

    def test_waiting_for_user_material_does_not_consume_active_runtime_limit(self):
        config,store,claim,files,under,p=self.setup_provider(max_task_seconds=1)
        worker=Worker(config,store,runner=None,clock=lambda:self.now[0])
        waiting=worker.publish(claim,'waiting_input',{'question':{'id':'q'}})
        self.now[0]+=120
        store.enqueue(claim['owner_id'],claim['id'],waiting['version'],{},max_queue=10)
        resumed=worker.claim();q=BudgetedProvider(config,store,files,resumed,under,clock=lambda:self.now[0])
        self.assertEqual(q.generate([{'role':'user','content':'resumed'}]).content,'{"ok":true}')

    def test_response_saved_before_ledger_commit_can_be_recovered(self):
        config,store,claim,files,under,p=self.setup_provider()
        messages=[{'role':'user','content':'one'}];first=p.generate(messages)
        with store.transaction() as db:db.execute("UPDATE provider_calls SET state='sent'")
        self.assertEqual(p.generate(messages),first);self.assertEqual(under.calls,1)
