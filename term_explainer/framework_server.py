"""Loopback-only, bounded background organization service. No file API."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
import threading
import time
from urllib.parse import urlsplit
import uuid
from .deepseek import DeepSeekClient,DeepSeekError
from .frameworks import FrameworkError,validate_input,input_hash,analyze_frameworks

class FrameworkJobs:
    def __init__(self,client_factory):
        self.client_factory=client_factory;self.lock=threading.Lock();self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='framework');self.records={};self.hashes={};self.closed=False
    def submit(self,payload,retry=False):
        payload=validate_input(payload);fingerprint=input_hash(payload)
        with self.lock:
            old=self.records.get(self.hashes.get(fingerprint))
            if old and not (retry and old['status']=='failed'):return deepcopy(old)
            if self.closed:raise FrameworkError('service_stopped','整理服务已停止。')
            if sum(r['status'] in ('queued','running') for r in self.records.values())>=5:raise FrameworkError('queue_full','已有任务正在整理，请稍后重试。')
            # Retain only a bounded metadata cache. Input documents are never logged.
            if len(self.records)>=256:
                for key,record in list(self.records.items()):
                    if record['status'] in ('complete','failed'):
                        self.records.pop(key);self.hashes.pop(record['inputHash'],None)
                        if len(self.records)<192:break
            task='task-'+uuid.uuid4().hex;row={'taskId':task,'inputHash':fingerprint,'status':'queued','createdAt':time.time()};self.records[task]=row;self.hashes[fingerprint]=task
            self.executor.submit(self.run,task,payload);return deepcopy(row)
    def run(self,task,payload):
        client=None
        with self.lock:self.records[task]['status']='running'
        try:
            client=self.client_factory();result=analyze_frameworks(payload,client)
            with self.lock:self.records[task].update(status='complete',result=result,calls=result['calls'],usage=result['usage'])
        except (DeepSeekError,FrameworkError) as error:
            with self.lock:self.records[task].update(status='failed',error={'code':error.code,'message':error.message},calls=client.calls if client else 0,usage=client.metrics[-1].get('usage',{}) if client and client.metrics else {})
        except Exception:
            with self.lock:self.records[task].update(status='failed',error={'code':'organization_failed','message':'整理任务未完成，已有资料不变；请检查本机服务。'},calls=client.calls if client else 0)
    def get(self,task):
        with self.lock:return deepcopy(self.records.get(task))
    def close(self):
        with self.lock:self.closed=True
        self.executor.shutdown(wait=False,cancel_futures=True)

class FrameworkHTTPServer(ThreadingHTTPServer):
    daemon_threads=True
    def server_close(self):
        super().server_close()
        if hasattr(self,'jobs'):self.jobs.close()

def make_server(*,host='127.0.0.1',port=8781,allowed_origins=('http://127.0.0.1:8773',),client_factory=None):
    if host!='127.0.0.1':raise ValueError('Framework service must bind only to 127.0.0.1')
    origins=set(allowed_origins)
    if not origins:raise ValueError('At least one exact local origin is required')
    for origin in origins:
        p=urlsplit(origin)
        if p.scheme!='http' or p.hostname!='127.0.0.1' or p.path or p.query or p.fragment or p.username or p.password or not p.port:raise ValueError('Only explicit loopback HTTP origins are allowed')
    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.1'
        def log_message(self,*args):pass
        def setup(self):super().setup();self.connection.settimeout(5)
        def send_json(self,status,value):
            body=json.dumps(value,ensure_ascii=False,allow_nan=False).encode('utf-8');self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('Connection','close')
            if self.headers.get('Origin') in origins:self.send_header('Access-Control-Allow-Origin',self.headers['Origin']);self.send_header('Vary','Origin')
            self.end_headers();self.wfile.write(body);self.close_connection=True
        def trusted(self):
            if len(self.headers.get_all('Origin',[]))!=1 or self.headers.get('Origin') not in origins or len(self.headers.get_all('Host',[]))!=1 or self.headers.get('Host')!='127.0.0.1:'+str(self.server.server_port):
                self.send_json(403,{'error':{'code':'untrusted_origin','message':'仅允许已配置的本地预览访问此整理服务。'}});return False
            return True
        def do_OPTIONS(self):
            if not self.trusted():return
            self.send_response(204);self.send_header('Access-Control-Allow-Origin',self.headers['Origin']);self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS');self.send_header('Access-Control-Allow-Headers','Content-Type, X-Framework-Retry');self.send_header('Access-Control-Max-Age','600');self.send_header('Content-Length','0');self.end_headers()
        def do_GET(self):
            if not self.trusted():return
            if self.path=='/health':self.send_json(200,{'ok':True,'providerConfigured':client_factory is not None or bool(os.environ.get('DEEPSEEK_API_KEY'))});return
            if self.path.startswith('/jobs/') and len(self.path)<230:
                row=self.server.jobs.get(self.path[6:])
                if row:self.send_json(200,row);return
            self.send_json(404,{'error':{'code':'not_found','message':'没有这个本机任务或接口。'}})
        def do_POST(self):
            if not self.trusted():return
            if self.path!='/jobs':self.send_json(404,{'error':{'code':'not_found','message':'接口不存在。'}});return
            lengths=self.headers.get_all('Content-Length',[])
            if self.headers.get('Transfer-Encoding') or len(lengths)!=1 or not lengths[0].isdigit():self.send_json(400,{'error':{'code':'invalid_length','message':'请求长度无效。'}});return
            size=int(lengths[0])
            if size>512*1024:self.send_json(413,{'error':{'code':'request_too_large','message':'概念摘要超过512KiB，未提交模型。'}});return
            if self.headers.get('Content-Type','').split(';')[0].strip()!='application/json':self.send_json(400,{'error':{'code':'invalid_type','message':'只接收概念摘要JSON。'}});return
            try:
                raw=self.rfile.read(size)
                if len(raw)!=size:raise ValueError('incomplete request')
                payload=json.loads(raw);row=self.server.jobs.submit(payload,retry=self.headers.get('X-Framework-Retry')=='1');self.send_json(202,{'taskId':row['taskId'],'status':row['status'],'inputHash':row['inputHash']})
            except FrameworkError as error:self.send_json(429 if error.code=='queue_full' else 400,{'error':{'code':error.code,'message':error.message}})
            except (ValueError,UnicodeError,TimeoutError):self.send_json(400,{'error':{'code':'invalid_json','message':'摘要格式无效或传输不完整，未提交模型。'}})
    server=FrameworkHTTPServer((host,port),Handler);server.jobs=FrameworkJobs(client_factory or (lambda:DeepSeekClient(max_calls=1,max_tokens=16384)));return server
