from unittest.mock import patch
from fastapi.testclient import TestClient
from term_explainer.online.api import create_app
from term_explainer.online.config import load_config
from term_explainer.online.store import OnlineStore
from term_explainer.online.auth import InviteAuth
from term_explainer.online.files import PrivateFiles
from tests.term_explainer.helpers import request_payload
from .helpers import OnlineCase

class APIBase(OnlineCase):
    def setUp(self):
        super().setUp();self.config=load_config(self.env);self.store=OnlineStore(self.config.private_root/'jobs.sqlite');self.files=PrivateFiles(self.config.private_root/'tasks')
        self.auth=InviteAuth(self.store,self.config);self.app=create_app(self.config,self.store,self.files,provider_enabled=True)
        self.client=TestClient(self.app,base_url=self.config.origin+self.config.api_prefix,root_path=self.config.api_prefix.rstrip('/'));self.addCleanup(self.client.close)
        self.headers={'Origin':self.config.origin}
    def login(self,client=None):
        client=client or self.client;secret=self.auth.create_invite('test');r=client.post('sessions',json={'invitation':secret},headers=self.headers)
        self.assertEqual(r.status_code,200,r.text)
        return {**self.headers,'X-CSRF-Token':r.json()['csrf']}
    def body(self):
        request=request_payload();request['sources']=[]
        return {'kind':'lesson','request':request,'documents':[],'model_allowed':True,'network_allowed':False}

class APITests(APIBase):
    def test_default_teaching_body_is_bounded_before_billable_work(self):
        h=self.login();h['Idempotency-Key']='body-budget'
        created=self.client.post('jobs',json=self.body(),headers=h).json()
        with self.store.connection() as db:
            import json
            job=json.loads(db.execute('SELECT body FROM jobs WHERE id=?',(created['id'],)).fetchone()['body'])
        self.assertEqual(job['manifest']['request']['max_body_chars'],4500)

    def test_material_reregistration_after_partial_upload_does_not_duplicate_slots(self):
        import hashlib
        h=self.login();h['Idempotency-Key']='two-materials';job=self.client.post('jobs',json=self.body(),headers=h).json()
        docs=[dict(name=str(i)+'.txt',title=str(i),mime='text/plain',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()) for i,raw in enumerate([b'first source',b'second source'])]
        registered=self.client.post('jobs/'+job['id']+'/materials',json={'version':job['version'],'documents':docs},headers=h).json()
        first=registered['uploads'][0]
        current=self.client.put('jobs/'+job['id']+'/sources/'+first['id'],content=b'first source',headers={**h,'Content-Type':'text/plain'}).json()
        reply=self.client.post('jobs/'+job['id']+'/materials',json={'version':current['version'],'documents':docs},headers=h)
        self.assertEqual(reply.status_code,200,reply.text)
        self.assertEqual(len(reply.json()['uploads']),2)
        self.assertTrue(reply.json()['uploads'][0]['uploaded'])

    def test_waiting_job_can_accept_additional_material_and_resume_same_identity(self):
        import hashlib
        h=self.login();h['Idempotency-Key']='supplement';job=self.client.post('jobs',json=self.body(),headers=h).json();owner=self.store.list_jobs(self.auth.authenticate(next(iter(self.client.cookies.values()))).owner_id)[0]['owner_id']
        draft=self.store.get_job(owner,job['id']);queued=self.store.transition(owner,job['id'],draft['version'],'queued',{});running=self.store.transition(owner,job['id'],queued['version'],'running',{})
        decision={'version':1,'action':'waiting_input','request':self.body()['request'],'sources':[],'readings':{},'selections':{},'question':{'id':'q-one','kind':'sources','messages':['需要原文。'],'candidates':[]}}
        waiting=self.store.transition(owner,job['id'],running['version'],'waiting_input',{'question':decision['question'],'checkpoint':{'documents':[],'decision':decision}})
        raw=b'Intro\nSource material.';descriptor={'name':'more.txt','title':'More','mime':'text/plain','bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
        r=self.client.post('jobs/'+job['id']+'/materials',json={'version':waiting['version'],'documents':[descriptor]},headers=h)
        self.assertEqual(r.status_code,200,r.text);new=r.json();self.assertEqual(new['id'],job['id'])
        source=new['uploads'][0];uploaded=self.client.put('jobs/'+job['id']+'/sources/'+source['id'],content=raw,headers={**h,'Content-Type':'text/plain'}).json()
        resumed=self.client.post('jobs/'+job['id']+'/answers',json={'version':uploaded['version'],'answer':{'question_id':'q-one','action':'resume_sources'}},headers=h)
        self.assertEqual(resumed.status_code,202,resumed.text);self.assertEqual(resumed.json()['state'],'queued')

    def test_session_cookie_and_idempotent_private_task_routes(self):
        h=self.login();h['Idempotency-Key']='one';r=self.client.post('jobs',json=self.body(),headers=h)
        self.assertEqual(r.status_code,201,r.text);job=r.json()
        self.assertEqual(self.client.post('jobs',json=self.body(),headers=h).json()['id'],job['id'])
        self.assertEqual(r.headers['Cache-Control'],'no-store')
        self.assertNotIn('owner_id',job);self.assertNotIn('manifest',job)
        start=self.client.post('jobs/'+job['id']+'/start',json={'version':job['version']},headers=h)
        self.assertEqual(start.status_code,202,start.text)
        self.assertEqual(self.client.get('jobs/'+job['id']).json()['state'],'queued')
        self.assertEqual(len(self.client.get('jobs').json()['jobs']),1)
        self.assertEqual(self.client.get('jobs/'+job['id']+'/result').status_code,409)

    def test_ready_artifact_is_returned_whole_and_unreadable_artifact_is_reported(self):
        # A lazily opened FileResponse would answer 200 with headers but no body
        # when the artifact is unreadable, which the browser shows as a dead
        # download; the route must ship the bytes or fail with a real error.
        h=self.login();h['Idempotency-Key']='result-download';job=self.client.post('jobs',json=self.body(),headers=h).json()
        owner=self.store.list_jobs(self.auth.authenticate(next(iter(self.client.cookies.values()))).owner_id)[0]['owner_id']
        draft=self.store.get_job(owner,job['id']);queued=self.store.transition(owner,job['id'],draft['version'],'queued',{})
        running=self.store.transition(owner,job['id'],queued['version'],'running',{})
        payload=b'PK\x03\x04internal-test-archive'
        artifact=self.files.path_for(job['id'],'lesson.zip');artifact.parent.mkdir(parents=True,exist_ok=True);artifact.write_bytes(payload)
        self.store.transition(owner,job['id'],running['version'],'complete',{'stage':'ready','result':{'asset_id':'lesson.zip','sha256':'0'*64,'bytes':len(payload)},'usage':{'calls':0}})
        r=self.client.get('jobs/'+job['id']+'/result',headers=h)
        self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.content,payload)
        self.assertIn('attachment',r.headers['content-disposition'])
        with patch('term_explainer.online.api.os.access',return_value=False):
            refused=self.client.get('jobs/'+job['id']+'/result',headers=h)
        self.assertEqual(refused.status_code,410,refused.text);self.assertEqual(refused.json()['error']['code'],'result_not_found')

    def test_other_invitation_cannot_read_answer_cancel_or_claim_result(self):
        h=self.login();h['Idempotency-Key']='one';job=self.client.post('jobs',json=self.body(),headers=h).json()
        other=TestClient(self.app,base_url=self.config.origin+self.config.api_prefix,root_path=self.config.api_prefix.rstrip('/'));self.addCleanup(other.close);oh=self.login(other)
        for method,path,body in [('GET','',None),('GET','/result',None),('POST','/cancel',{'version':1}),('POST','/answers',{'version':1})]:
            with self.subTest(path=path):
                r=other.request(method,'jobs/'+job['id']+path,json=body,headers=oh);self.assertEqual(r.status_code,404,r.text)

    def test_upload_digest_checked_before_queue_and_budget_queue_is_bounded(self):
        import hashlib
        body=self.body();raw=b'Intro\nUseful text.'
        body['documents']=[{'name':'paper.txt','title':'Paper','mime':'text/plain','bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}]
        h=self.login();h['Idempotency-Key']='source';job=self.client.post('jobs',json=body,headers=h).json()
        self.assertEqual(self.client.post('jobs/'+job['id']+'/start',json={'version':job['version']},headers=h).status_code,409)
        upload=job['uploads'][0]
        r=self.client.put('jobs/'+job['id']+'/sources/'+upload['id'],content=raw,headers={**h,'Content-Type':'text/plain'})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(self.client.post('jobs/'+job['id']+'/start',json={'version':r.json()['version']},headers=h).status_code,202)
