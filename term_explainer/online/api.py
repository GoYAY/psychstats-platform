"""Invitation-scoped API. No generation runs inside HTTP requests."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import asyncio,hashlib,json,os,re,time,tempfile,uuid
from contextlib import asynccontextmanager,suppress
from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse,Response
from .auth import InviteAuth,hashed
from .config import OnlineError
from .store import canonical,TERMINAL,digest
from .worker import Worker
from .sources import apply_answer
from .files import cleanup_jobs
from ..contract import validate_request
from ..library_export import public_catalogue
from ..frameworks import validate_input

def create_app(config,store,files,*,provider_enabled=False,clock=time.time,cleanup_interval=60):
    async def maintenance():
        import logging
        while True:
            try:
                failures=await asyncio.to_thread(cleanup_jobs,store,files,clock())
                if failures:logging.getLogger(__name__).warning('private_cleanup_retry_required count=%d',len(failures))
            except Exception:logging.getLogger(__name__).error('private_cleanup_retry_required')
            await asyncio.sleep(cleanup_interval)
    @asynccontextmanager
    async def lifespan(app):
        task=asyncio.create_task(maintenance())
        try:yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):await task
    app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifespan)
    auth=InviteAuth(store,config,clock=clock);cookie_name='term_beta_'+hashlib.sha256(config.api_prefix.encode()).hexdigest()[:10]
    Worker(config,store,runner=None,clock=clock)  # schema only, no background calls
    with store.connection() as db:db.execute('CREATE TABLE IF NOT EXISTS rate_limits(key TEXT PRIMARY KEY,window INTEGER NOT NULL,count INTEGER NOT NULL)')

    def dto(job):
        result=dict(id=job['id'],kind=job['kind'],state=job['state'],stage=job['stage'],version=job['version'],progress=job['progress'],question=job['question'],resultAvailable=job['state']=='complete' and job['result'] is not None,expiresAt=(job['terminal_at'] or job['updated_at'])+86400,usage=job['usage'])
        result['usage']=store.job_usage(job['id'],files=files)
        if job['state'] in {'draft','waiting_input'}:result['uploads']=[{k:d[k] for k in ('id','name','mime','bytes','sha256','uploaded')} for d in job['manifest'].get('documents',[])]
        result['termName']=job['manifest'].get('request',{}).get('term',{}).get('zh','知识关系整理' if job['kind']=='organize' else '已清理的临时任务')
        return result

    @app.middleware('http')
    async def privacy(request,call_next):
        request.state.request_id=uuid.uuid4().hex
        try:
            if request.headers.get('host')!=config.origin.split('://',1)[1]:raise OnlineError('untrusted_host','请求来源无效。',403)
            if request.headers.get('origin') not in (None,config.origin):raise OnlineError('untrusted_origin','请求来源无效。',403)
            if request.method not in {'GET','HEAD'} and request.headers.get('origin')!=config.origin:raise OnlineError('untrusted_origin','请求来源无效。',403)
            response=await call_next(request)
        except OnlineError as error:response=JSONResponse({'error':{'code':error.code,'message':error.message},'requestId':request.state.request_id},status_code=error.status)
        except Exception:response=JSONResponse({'error':{'code':'request_failed','message':'请求未完成，请重新读取任务状态。'},'requestId':request.state.request_id},status_code=500)
        response.headers['Cache-Control']='no-store';response.headers['X-Content-Type-Options']='nosniff';response.headers['X-Request-ID']=request.state.request_id;return response

    @app.exception_handler(OnlineError)
    async def online_error(request,error):return JSONResponse({'error':{'code':error.code,'message':error.message},'requestId':request.state.request_id},status_code=error.status)

    def session(request,*,mutate=False):
        value=auth.authenticate(request.cookies.get(cookie_name))
        if mutate and not auth.validate_csrf(value,request.headers.get('x-csrf-token')):raise OnlineError('csrf_failed','请重新验证内测会话。',403)
        if mutate:rate('write:'+hashed(value.owner_id),60)
        return value

    async def receive(request,sink,maximum):
        lengths=request.headers.getlist('content-length')
        if len(lengths)>1 or (lengths and (not re.fullmatch(r'[0-9]+',lengths[0]) or len(lengths[0])>12)):raise OnlineError('invalid_length','请求长度无效。')
        if lengths and int(lengths[0])>maximum:raise OnlineError('request_too_large','请求超过接收限制。',413)
        count=0;hasher=hashlib.sha256()
        try:
            async with asyncio.timeout(config.limits.request_timeout):
                async for chunk in request.stream():
                    count+=len(chunk)
                    if count>maximum:raise OnlineError('request_too_large','请求超过接收限制。',413)
                    sink.write(chunk);hasher.update(chunk)
        except TimeoutError:raise OnlineError('upload_timeout','资料接收超时，请保留本机文件后重试。',408) from None
        if lengths and count!=int(lengths[0]):raise OnlineError('invalid_length','实际请求长度不符。')
        return count,hasher.hexdigest()

    async def body(request,*,maximum=1024*1024):
        if request.headers.get('content-type','').split(';')[0]!='application/json':raise OnlineError('invalid_content_type','请提交JSON请求。')
        sink=BytesIO();await receive(request,sink,maximum);raw=sink.getvalue()
        try:value=json.loads(raw)
        except (ValueError,UnicodeError):raise OnlineError('invalid_json','请求JSON无效。') from None
        if not isinstance(value,dict):raise OnlineError('invalid_json','请求必须是JSON对象。')
        return value

    def enabled():
        if not provider_enabled:raise OnlineError('generation_disabled','生成服务暂未启用，已保存内容仍可阅读。',503)

    def rate(key,limit):
        window=int(clock()//60)
        with store.transaction() as db:
            row=db.execute('SELECT window,count FROM rate_limits WHERE key=?',(key,)).fetchone()
            count=row['count'] if row and row['window']==window else 0
            if count>=limit:raise OnlineError('rate_limited','验证尝试较多，请稍后再试。',429)
            db.execute('INSERT INTO rate_limits VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET window=excluded.window,count=excluded.count',(key,window,count+1))
            db.execute('DELETE FROM rate_limits WHERE window<?',(window-2,))

    @app.get('/health')
    async def health():return {'ok':True,'generationEnabled':bool(provider_enabled),'version':'online-beta-1'}

    @app.post('/sessions')
    async def login(request:Request):
        rate('login:'+hashed(request.client.host if request.client else 'unknown'),8);rate('login:global',60)
        data=await body(request,maximum=1024)
        if set(data)!={'invitation'}:raise OnlineError('invalid_request','邀请验证字段无效。')
        s=auth.exchange(data['invitation']);response=JSONResponse({'csrf':s.csrf,'expiresAt':s.expires_at})
        response.set_cookie(cookie_name,s.token,max_age=max(1,int(s.expires_at-clock())),path=config.api_prefix,secure=True,httponly=True,samesite='strict')
        return response

    @app.get('/session')
    async def who(request:Request):
        s=session(request)
        return {'csrf':s.csrf,'expiresAt':s.expires_at,'generationEnabled':bool(provider_enabled),'limits':{'files':config.limits.max_files,'fileBytes':config.limits.max_file_bytes,'totalBytes':config.limits.max_total_bytes}}

    @app.delete('/session')
    async def logout(request:Request):
        auth.logout(session(request,mutate=True));response=JSONResponse({'ok':True});response.delete_cookie(cookie_name,path=config.api_prefix,secure=True,httponly=True,samesite='strict');return response

    def manifest(value,owner,key):
        if set(value)-{'kind','request','input','documents','model_allowed','network_allowed'}:raise OnlineError('invalid_request','生成请求含不支持的字段。')
        if value.get('kind') not in {'lesson','organize'} or any(type(value.get(k)) is not bool for k in ('model_allowed','network_allowed')):raise OnlineError('invalid_request','任务类型或授权字段无效。')
        value=deepcopy(value)
        if value['kind']=='organize':
            if value.get('documents') or value.get('request'):raise OnlineError('invalid_request','整理任务不接收文献或科普正文。')
            try:value['input']=validate_input(value.get('input'))
            except Exception:raise OnlineError('invalid_request','知识整理摘要格式无效。') from None
            return value
        request=value.get('request')
        if not isinstance(request,dict):raise OnlineError('invalid_request','缺少术语请求。')
        # Browser-provided catalogue URLs never become authoritative public links.
        catalogue=public_catalogue(config.public_root)['terms']
        request['catalog']=[{k:t[k] for k in ('id','zh','en','aliases')}|{'kind':'classic'} for t in catalogue]
        request['network_allowed']=value['network_allowed']
        request.setdefault('max_body_chars',4500)
        try:validate_request(request)
        except (ValueError,KeyError,TypeError):raise OnlineError('invalid_request','术语、定义或相关概念格式无效。') from None
        docs=value.get('documents',[])
        if not isinstance(docs,list) or len(docs)>config.limits.max_files:raise OnlineError('upload_limit','文件数量超过限制。',413)
        total=0;result=[]
        for index,d in enumerate(docs):
            if not isinstance(d,dict) or set(d)-{'name','title','mime','bytes','sha256'}:raise OnlineError('invalid_document','文献描述无效。')
            if d.get('mime') not in {'application/pdf','text/plain'} or type(d.get('bytes')) is not int or not 1<=d['bytes']<=config.limits.max_file_bytes:raise OnlineError('invalid_document','文件类型或大小无效。')
            if not isinstance(d.get('name'),str) or not 1<=len(d['name'])<=200 or any(c in d['name'] for c in '/\\\x00'):raise OnlineError('invalid_document','文件名无效。')
            if not isinstance(d.get('sha256'),str) or not re.fullmatch(r'[a-f0-9]{64}',d['sha256']):raise OnlineError('invalid_document','文件指纹无效。')
            if not isinstance(d.get('title',d['name']),str) or len(d.get('title',d['name']))>500:raise OnlineError('invalid_document','文献标题过长。')
            sid='source-'+hashlib.sha256((owner+'|'+key+'|'+str(index)).encode()).hexdigest()[:24]
            total+=d['bytes'];result.append({**d,'id':sid,'asset_id':sid+('.pdf' if d['mime']=='application/pdf' else '.txt'),'uploaded':False})
        if total>config.limits.max_total_bytes:raise OnlineError('upload_limit','文献总大小超过限制。',413)
        value['documents']=result;return value

    @app.get('/jobs')
    async def list_jobs(request:Request):return {'jobs':[dto(j) for j in store.list_jobs(session(request).owner_id)]}

    @app.post('/jobs',status_code=201)
    async def create(request:Request):
        owner=session(request,mutate=True).owner_id;enabled();key=request.headers.get('idempotency-key','')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',key):raise OnlineError('invalid_request','缺少有效提交标识。')
        value=manifest(await body(request),owner,key)
        rate('create:'+hashed(owner),10)
        return dto(store.create_job(owner,key,value,max_pending=config.limits.max_queue))

    @app.get('/jobs/{job_id}')
    async def get(job_id:str,request:Request):return dto(store.get_job(session(request).owner_id,job_id))

    @app.put('/jobs/{job_id}/sources/{source_id}')
    async def upload(job_id:str,source_id:str,request:Request):
        owner=session(request,mutate=True).owner_id;enabled();job=store.get_job(owner,job_id)
        if job['state'] not in {'draft','waiting_input'}:raise OnlineError('invalid_transition','任务已开始，不能替换输入。',409)
        descriptor=next((d for d in job['manifest'].get('documents',[]) if d['id']==source_id),None)
        if descriptor is None:raise OnlineError('not_found','文献不存在。',404)
        if request.headers.get('content-type','').split(';')[0]!=descriptor['mime']:raise OnlineError('invalid_content_type','文件类型与声明不符。')
        with tempfile.SpooledTemporaryFile(max_size=65536,dir=config.private_root) as stream:
            size,sha=await receive(request,stream,descriptor['bytes'])
            if size!=descriptor['bytes'] or sha!=descriptor['sha256']:raise OnlineError('digest_mismatch','文件指纹不符，请重新选择文件。')
            stream.seek(0);files.put(job_id,descriptor['asset_id'],stream,config.limits)
        value=deepcopy(job['manifest']);next(d for d in value['documents'] if d['id']==source_id)['uploaded']=True
        return dto(store.transition(owner,job_id,job['version'],job['state'],{'manifest':value}))

    @app.post('/jobs/{job_id}/start',status_code=202)
    async def start(job_id:str,request:Request):
        owner=session(request,mutate=True).owner_id;enabled();job=store.get_job(owner,job_id);data=await body(request)
        if set(data)!={'version'}:raise OnlineError('invalid_request','任务启动字段无效。')
        if type(data['version']) is not int:raise OnlineError('invalid_request','任务版本必须是整数。')
        if job['manifest'].get('model_allowed') is not True:raise OnlineError('model_consent_required','请确认资料发送和模型使用。',403)
        if any(not d['uploaded'] for d in job['manifest'].get('documents',[])):raise OnlineError('upload_incomplete','文献尚未上传完成。',409)
        if job['state']!='draft':raise OnlineError('invalid_transition','请通过当前确认问题继续任务。',409)
        return dto(store.enqueue(owner,job_id,data['version'],{},max_queue=config.limits.max_queue))

    @app.post('/jobs/{job_id}/materials')
    async def materials(job_id:str,request:Request):
        owner=session(request,mutate=True).owner_id;enabled();job=store.get_job(owner,job_id);data=await body(request)
        if set(data)!={'version','documents'} or type(data['version']) is not int:raise OnlineError('invalid_request','补充材料请求无效。')
        if job['state'] not in {'draft','waiting_input'}:raise OnlineError('invalid_transition','执行中的输入不能替换。',409)
        fingerprint=digest(data)
        if job['manifest'].get('last_material_input')==fingerprint:return dto(job)
        if data['version']!=job['version']:raise OnlineError('stale_version','任务已更新，请重新读取。',409)
        parsed=manifest(dict(kind='lesson',request=job['manifest']['request'],documents=data['documents'],model_allowed=True,network_allowed=job['manifest']['network_allowed']),owner,job_id+'-'+str(job['version']))
        existing=job['manifest'].get('documents',[])
        fingerprints={(d['sha256'],d['bytes'],d['mime']) for d in existing}
        additions=[]
        for d in parsed['documents']:
            key=(d['sha256'],d['bytes'],d['mime'])
            if key not in fingerprints:additions.append(d);fingerprints.add(key)
        if not additions:return dto(job)
        documents=existing+additions
        if len(documents)>config.limits.max_files or sum(d['bytes'] for d in documents)>config.limits.max_total_bytes:raise OnlineError('upload_limit','补充后资料超过本轮限制。',413)
        value=deepcopy(job['manifest']);value.update(documents=documents,last_material_input=fingerprint)
        checkpoint=deepcopy(job.get('checkpoint') or {});checkpoint.pop('documents',None)
        return dto(store.transition(owner,job_id,job['version'],job['state'],{'manifest':value,'checkpoint':checkpoint}))

    @app.post('/jobs/{job_id}/answers',status_code=202)
    async def answer(job_id:str,request:Request):
        owner=session(request,mutate=True).owner_id;enabled();job=store.get_job(owner,job_id);data=await body(request)
        if type(data.get('version')) is not int or job['state']!='waiting_input' or data.get('version')!=job['version']:raise OnlineError('stale_question','任务问题已更新。',409)
        if set(data)-{'version','answer'}:raise OnlineError('invalid_request','回答字段无效。')
        if (job.get('question') or {}).get('kind')=='recovery':raise OnlineError('invalid_transition','请使用专用继续入口。',409)
        checkpoint=deepcopy(job['checkpoint']);decision=checkpoint['decision']
        if data.get('answer',{}).get('action')=='resume_sources':
            documents=job['manifest'].get('documents',[])
            if not documents or any(not d['uploaded'] for d in documents):raise OnlineError('upload_incomplete','请先完成补充文献上传。',409)
        checkpoint['decision']=apply_answer(decision,data.get('answer',{}),decision['version'])
        value=deepcopy(job['manifest'])
        value['network_allowed']=checkpoint['decision']['request']['network_allowed']
        return dto(store.enqueue(owner,job_id,job['version'],{'checkpoint':checkpoint,'question':None,'manifest':value},max_queue=config.limits.max_queue))

    @app.post('/jobs/{job_id}/resume',status_code=202)
    async def resume(job_id:str,request:Request):
        owner=session(request,mutate=True).owner_id;enabled();job=store.get_job(owner,job_id);data=await body(request)
        if set(data)!={'version'} or type(data['version']) is not int:raise OnlineError('invalid_request','继续请求无效。')
        if data['version']!=job['version']:raise OnlineError('stale_version','任务已更新，请重新读取。',409)
        from .recovery import require_recoverable,reserve_recovery
        require_recoverable(job,store,files,config)
        checkpoint=reserve_recovery(job)
        return dto(store.enqueue(owner,job_id,job['version'],{'checkpoint':checkpoint,'question':None},max_queue=config.limits.max_queue))

    @app.post('/jobs/{job_id}/cancel')
    async def cancel(job_id:str,request:Request):
        owner=session(request,mutate=True).owner_id;job=store.get_job(owner,job_id);data=await body(request)
        if set(data)!={'version'}:raise OnlineError('invalid_request','取消字段无效。')
        return dto(store.transition(owner,job_id,data['version'],'cancelled',{}))

    @app.get('/jobs/{job_id}/result')
    async def result(job_id:str,request:Request):
        job=store.get_job(session(request).owner_id,job_id)
        if job['state']!='complete' or not job['result']:raise OnlineError('result_not_ready','结果尚不可领取。',409)
        if clock()-job['terminal_at']>86400:raise OnlineError('result_expired','临时产物已过期，请阅读已保存的本机副本。',410)
        path=files.path_for(job_id,job['result']['asset_id'])
        # FileResponse opens the path lazily, so an unreadable artifact would send
        # headers and then no body: the browser sees a dead download with no error.
        # Read the artifact up front so any IO problem becomes an explicit 410.
        if not path.is_file() or not os.access(path,os.R_OK):raise OnlineError('result_not_found','临时产物已清理。',410)
        try:payload=path.read_bytes()
        except OSError:raise OnlineError('result_not_found','临时产物已清理。',410) from None
        if job['kind']=='organize':return JSONResponse(json.loads(payload))
        return Response(payload,media_type='application/zip',headers={'Content-Disposition':'attachment; filename="term-explanation.zip"'})

    return app
