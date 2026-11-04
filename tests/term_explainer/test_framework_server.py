import importlib
import json
import threading
import time
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from term_explainer.deepseek import DeepSeekClient
from tests.term_explainer.test_frameworks import payload,output
try:api=importlib.import_module('term_explainer.framework_server')
except ModuleNotFoundError:api=None

class FrameworkServerTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(api,'Loopback framework server missing');self.sent=[]
        def transport(*args):
            self.sent.append(args)
            return {'model':'deepseek-flash','usage':{'prompt_tokens':20,'completion_tokens':30,'total_tokens':50},'choices':[{'message':{'content':json.dumps(output())},'finish_reason':'stop'}]}
        self.server=api.make_server(port=0,client_factory=lambda:DeepSeekClient(api_key='test-only',max_calls=1,transport=transport))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.base='http://127.0.0.1:'+str(self.server.server_port)
    def tearDown(self):
        if hasattr(self,'server'):self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
    def request(self,path='/jobs',value=None,headers=None):
        body=json.dumps(value).encode() if value is not None else None
        h={'Origin':'http://127.0.0.1:8773','Content-Type':'application/json',**(headers or {})}
        try:
            with urlopen(Request(self.base+path,data=body,headers=h),timeout=5) as response:return response.status,json.load(response)
        except HTTPError as error:return error.code,json.load(error)
    def finished(self,task):
        for _ in range(100):
            status,result=self.request('/jobs/'+task)
            if result['status'] in ('complete','failed'):return result
            time.sleep(.01)
        self.fail('Local job failed to finish')
    def test_valid_job_is_async_and_identical_request_reuses_one_actual_call(self):
        status,value=self.request(value=payload());self.assertEqual(status,202)
        done=self.finished(value['taskId']);self.assertEqual(done['status'],'complete');self.assertEqual(done['result']['calls'],1)
        _,same=self.request(value=payload());self.assertEqual(same['taskId'],value['taskId']);self.assertEqual(len(self.sent),1)
    def test_external_missing_origin_rebinding_host_and_invalid_body_do_not_call_provider(self):
        for headers in [{'Origin':'https://evil.example'},{'Origin':''},{'Host':'evil.example'},{'Content-Length':'600000'}]:
            status,_=self.request(value=payload(),headers=headers);self.assertIn(status,[400,403,413])
        status,_=self.request(value={**payload(),'raw_pdf':'secret'});self.assertEqual(status,400);self.assertEqual(len(self.sent),0)
    def test_no_file_endpoint_and_no_public_binding(self):
        self.assertEqual(self.server.server_address[0],'127.0.0.1')
        self.assertEqual(self.request('/C:/private')[0],404)
        with self.assertRaises(ValueError):api.make_server(host='0.0.0.0',port=0)
    def test_missing_key_is_readable_and_never_calls_provider(self):
        self.server.jobs.client_factory=lambda:DeepSeekClient(api_key='',max_calls=1)
        _,value=self.request(value=payload());done=self.finished(value['taskId'])
        self.assertEqual(done['status'],'failed');self.assertIn('error',done);self.assertEqual(len(self.sent),0)
    def test_concurrent_jobs_are_bounded_and_unknown_job_is_404(self):
        self.assertEqual(self.request('/jobs/not-a-job')[0],404)
        gate=threading.Event();started=threading.Event()
        def transport(*args):
            started.set();gate.wait(timeout=3)
            return {'model':'deepseek-flash','usage':{'prompt_tokens':20,'completion_tokens':30,'total_tokens':50},'choices':[{'message':{'content':json.dumps(output())},'finish_reason':'stop'}]}
        self.server.jobs.client_factory=lambda:DeepSeekClient(api_key='test-only',max_calls=1,transport=transport)
        try:
            self.assertEqual(self.request(value=payload())[0],202);self.assertTrue(started.wait(1))
            for i in range(4):
                p=payload();p['terms'][0]['name']+=str(i);self.assertEqual(self.request(value=p)[0],202)
            p=payload();p['terms'][0]['name']+='overflow';self.assertEqual(self.request(value=p)[0],429)
        finally:gate.set()

if __name__=='__main__':unittest.main()
