import json
from term_explainer.online.orchestrator import advance_job
from term_explainer.online.files import PrivateFiles
from term_explainer.online.provider import BudgetedProvider
from term_explainer.online.worker import Worker
from term_explainer.deepseek import DeepSeekClient
from tests.term_explainer.helpers import request_payload,result_payload
from tests.term_explainer.test_pipeline import analysis_payload
from .test_jobs import QueueFixture

class OrchestratorTests(QueueFixture):
    def test_disabled_policy_resumed_new_story_makes_zero_provider_calls(self):
        from term_explainer.online.config import OnlineError
        from term_explainer.pipeline import prepare_evidence
        from tests.term_explainer.test_pipeline import ExternalDouble
        config,store,owner,original=self.queue();store.transition(owner,original['id'],original['version'],'cancelled',{})
        request=request_payload();lesson=result_payload();lesson['visual']['presentation']=dict(version=1,focus='structure',numeric_role='none',layout='story',interaction='none')
        evidence=prepare_evidence(__import__('term_explainer.contract',fromlist=['validate_request']).validate_request(request),ExternalDouble([analysis_payload()])).evidence
        job=store.create_job(owner,'disabled-resume',dict(kind='lesson',request=request,model_allowed=True,network_allowed=False,documents=[]))
        store.enqueue(owner,job['id'],job['version'],dict(checkpoint=dict(documents=[],decision=dict(action='ready',request=request,sources=request['sources'],evidence=evidence),lesson=lesson)),max_queue=10)
        worker=Worker(config,store,runner=None,clock=lambda:self.now[0]);claim=worker.claim();files=PrivateFiles(config.private_root/'tasks')
        class External:
            def generate(self,*a,**kw):raise AssertionError('Rollback must not send')
        provider=BudgetedProvider(config,store,files,claim,External(),clock=lambda:self.now[0])
        with self.assertRaises(OnlineError) as caught:advance_job(claim,store,files,provider)
        self.assertEqual(caught.exception.code,'visual_review_required');self.assertEqual(provider.calls,0)

    def test_complete_job_uses_real_pipeline_and_repeat_claim_is_zero_new_calls(self):
        config,store,owner,original=self.queue();store.transition(owner,original['id'],original['version'],'cancelled',{})
        request=request_payload();job=store.create_job(owner,'complete',{'kind':'lesson','request':request,'model_allowed':True,'network_allowed':False,'documents':[]})
        store.transition(owner,job['id'],job['version'],'queued',{})
        worker=Worker(config,store,runner=None,clock=lambda:self.now[0]);claim=worker.claim();files=PrivateFiles(config.private_root/'tasks')
        replies=[analysis_payload(),result_payload()];sent=[]
        def transport(url,payload,headers,timeout):
            sent.append(payload)
            return {'model':'deepseek-flash','usage':{'prompt_tokens':10,'completion_tokens':20,'total_tokens':30},'choices':[{'finish_reason':'stop','message':{'content':json.dumps(replies.pop(0),ensure_ascii=False)}}]}
        raw=DeepSeekClient(api_key='offline-placeholder',max_calls=5,transport=transport)
        provider=BudgetedProvider(config,store,files,claim,raw,clock=lambda:self.now[0])
        result=advance_job(claim,store,files,provider)
        self.assertEqual(result['state'],'complete');self.assertEqual(len(sent),2)
        self.assertIsNone(worker.claim());self.assertEqual(len(sent),2)
        self.assertTrue(files.path_for(job['id'],result['result']['asset_id']).is_file())
        import zipfile
        with zipfile.ZipFile(files.path_for(job['id'],result['result']['asset_id'])) as archive:
            package=json.loads(archive.read('library.json'))
            provenance=package['revisions'][0]['provenance']
            self.assertEqual(provenance['document_readings'],[])
            self.assertEqual(provenance['human_scientific_review'],'pending')

    def test_missing_literature_pauses_and_does_not_generate_lesson(self):
        config,store,owner,original=self.queue()
        store.transition(owner,original['id'],original['version'],'cancelled',{})
        request=request_payload();request.update(sources=[],literature_prompted=False)
        job=store.create_job(owner,'new',{'kind':'lesson','request':request,'model_allowed':True,'network_allowed':False,'documents':[]})
        store.transition(owner,job['id'],job['version'],'queued',{})
        claim=Worker(config,store,runner=lambda j:None,clock=lambda:self.now[0]).claim();files=PrivateFiles(config.private_root/'tasks')
        class External:
            def generate(self,*a,**k):raise AssertionError('No model call before source prompt')
        provider=BudgetedProvider(config,store,files,claim,External(),clock=lambda:self.now[0])
        result=advance_job(claim,store,files,provider)
        self.assertEqual(result['state'],'waiting_input');self.assertEqual(result['question']['kind'],'literature')
        self.assertEqual(provider.calls,0)
