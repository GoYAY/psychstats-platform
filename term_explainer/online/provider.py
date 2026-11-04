"""Persistent upper-bound reservations and cached transport responses."""
from dataclasses import asdict
from datetime import datetime,timezone
from io import BytesIO
import json,time
from .config import OnlineError
from .store import canonical,digest
from .worker import require_lease,active_runtime
from ..deepseek import ModelReply,DeepSeekError,safe_public_url,parse_model_reply

KNOWN_ACCESS_ERRORS={'provider_http_403','provider_http_404','source_unavailable','source_access_blocked'}
KNOWN_RESPONSE_ERRORS=KNOWN_ACCESS_ERRORS|{'model_truncated','model_incomplete','empty_model_response','invalid_provider_response'}
# An HTTP error status is a confirmed non-delivery: the provider refused or failed the
# request instead of returning a completion, so nothing needs reconciliation and the very
# same request may be re-sent. Ambiguous transports (timeout, broken connection) are NOT
# retried here; they stay reserved until a human reconciles them.
TRANSIENT_HTTP_ERRORS={'provider_http_429','provider_http_500','provider_http_502','provider_http_503','provider_http_504'}
TRANSPORT_RETRY_DELAYS=(1.0,3.0)

def _wire_shape(value,depth=0):
    """Skeleton of a request body: types, keys and sizes, never its text."""
    if depth>4:return dict(type=type(value).__name__)
    if isinstance(value,str):return dict(type='str',chars=len(value))
    if isinstance(value,dict):return dict(type='dict',keys=sorted(str(k) for k in value)[:24],
                                          items={str(k):_wire_shape(v,depth+1) for k,v in list(value.items())[:24]})
    if isinstance(value,(list,tuple)):return dict(type='list',len=len(value),items=[_wire_shape(v,depth+1) for v in value[:8]])
    if isinstance(value,(int,float)) and not isinstance(value,bool):return dict(type=type(value).__name__,value=value)
    return dict(type=type(value).__name__)

class BudgetedProvider:
    def __init__(self,config,store,files,job,provider,*,clock=time.time):
        self.config=config;self.store=store;self.files=files;self.job=job;self.provider=provider;self.clock=clock
        self.model=getattr(provider,'model','deepseek-flash');self.metrics=[];self.phase='online'
        # Key of the reservation created by the attempt in flight, used to release it on
        # a confirmed non-delivery. Cached receipts never set it, so they are never dropped.
        self._fresh_key=None

    @property
    def calls(self):
        with self.store.connection() as db:return db.execute('SELECT COUNT(*) FROM provider_calls WHERE job_id=?',(self.job['id'],)).fetchone()[0]

    def generate(self,messages,reasoning_effort='high'):return self._call('generate',{'messages':messages,'reasoning_effort':reasoning_effort})
    def search(self,query):return self._call('search',{'query':query})
    def fetch(self,url,*,source_id,origin='search'):
        safe_public_url(url)
        return self._call('fetch',dict(url=url,source_id=source_id,origin=origin))

    def _call(self,operation,arguments):
        for delay in (*TRANSPORT_RETRY_DELAYS,None):
            self._fresh_key=None
            try:
                result=self._attempt(operation,arguments)
                self._fresh_key=None
                return result
            except DeepSeekError as error:
                key,self._fresh_key=self._fresh_key,None
                if key is None or error.code not in TRANSIENT_HTTP_ERRORS:raise
                # Nothing was delivered or billed: release the reservation so the
                # byte-identical request can be re-sent instead of stalling the job.
                # A receipt already cached by this attempt keeps its failed_known row.
                with self.store.transaction() as db:
                    db.execute("DELETE FROM provider_calls WHERE job_id=? AND key=? AND state='sent'",(self.job['id'],key))
                self.store.audit(self.job['id'],dict(stage=self.phase,error_code=error.code,outcome='transport_retry'))
                if delay is None:raise
                time.sleep(delay)

    def _attempt(self,operation,arguments):
        network=operation!='generate'
        if network and not self.job['manifest'].get('network_allowed',False):raise OnlineError('network_consent_required','本任务尚未授权联网。',403)
        base_key=digest(dict(operation=operation,arguments=arguments))
        recovery=(self.job.get('checkpoint') or {}).get('recovery_requests',{}).get(base_key)
        if not network and recovery:
            # Explicit user continuation changes ONLY the failed generation step.
            # Persisted nonce and prior receipt make restart byte-identical/cacheable.
            prior=self.files.path_for(self.job['id'],'response-'+recovery['prior_key']+'.json')
            if not prior.is_file():raise OnlineError('needs_reconciliation','修复所需回执不可用，不能自动重发。',409)
            saved=json.loads(prior.read_bytes())
            content=saved.get('content')
            if not isinstance(content,str):raise OnlineError('needs_reconciliation','修复所需响应需核对，不能自动重发。',409)
            repaired_messages=[*arguments['messages'],dict(role='assistant',content=content),
                dict(role='user',content=('上次结构校验未通过。请依据原合同和提供的证据修正完整 JSON；保留原术语、文献身份和必要内容，不通过删除候选或虚构证据绕过校验。'
                +'校验类别：'+recovery['code']+'；本次明确授权的局部修复编号：'+str(recovery['attempt'])))]
            arguments={'messages':repaired_messages,'reasoning_effort':'low'}
        if not network:
            pending=arguments.get('messages')
            # A single malformed message shape wastes a paid vendor round-trip and only
            # surfaces as an opaque 4xx, so refuse it here instead.
            if (not isinstance(pending,list) or not pending
                or not all(isinstance(m,dict) and isinstance(m.get('role'),str) and isinstance(m.get('content'),str) for m in pending)):
                raise OnlineError('invalid_wire_request','消息结构不合法，已阻止发送。',400)
        key=digest(dict(operation=operation,arguments=arguments));limits=self.config.limits
        # UTF-8 byte count is a conservative input-token bound, plus framing reserve.
        reserve=len(canonical(arguments).encode())+4096+limits.max_output_tokens if not network else 0
        day=datetime.fromtimestamp(self.clock(),timezone.utc).date().isoformat();asset='response-'+key+'.json'
        with self.store.transaction() as db:
            current=require_lease(db,self.store,self.job,self.clock())
            if active_runtime(current,self.clock())>=limits.max_task_seconds:
                raise OnlineError('task_timeout','本轮任务运行时间已达到安全上限。',409)
            old=db.execute('SELECT * FROM provider_calls WHERE job_id=? AND key=?',(self.job['id'],key)).fetchone()
            if old:
                path=self.files.path_for(self.job['id'],asset)
                if not path.is_file():raise OnlineError('needs_reconciliation','此前请求的响应未确认，不自动重发。',409)
                saved=json.loads(path.read_bytes())
                if isinstance(saved,dict) and '_envelope' in saved:
                    envelope=saved['_envelope']
                    try:saved=asdict(parse_model_reply(envelope))
                    except DeepSeekError as error:saved={'_known_error':error.code,'usage':envelope.get('usage',{}) if isinstance(envelope,dict) else {}}
                    raw=canonical(saved).encode();self.files.put(self.job['id'],asset,BytesIO(raw),limits)
                if isinstance(saved,dict) and saved.get('_known_error') in KNOWN_RESPONSE_ERRORS:
                    actual=saved.get('usage',{}).get('total_tokens') if isinstance(saved.get('usage'),dict) else None
                    if type(actual) is not int or not 0<=actual<=old['reserved_tokens']:actual=old['reserved_tokens']
                    db.execute("UPDATE provider_calls SET state='failed_known',reserved_tokens=? WHERE job_id=? AND key=?",(actual,self.job['id'],key))
                    error=DeepSeekError(saved['_known_error'],'此前响应未通过校验；已保留回执，未重新发送请求。');error.response_received=True;raise error
                if old['state']!='received':
                    usage=saved.get('usage',{}).get('total_tokens') if operation=='generate' else 0
                    if type(usage) is not int or not 0<=usage<=old['reserved_tokens']:raise OnlineError('needs_reconciliation','已存响应需核对，不自动重发。',409)
                    db.execute("UPDATE provider_calls SET state='received',reserved_tokens=? WHERE job_id=? AND key=?",(usage,self.job['id'],key))
                if not network:self.last_generation=dict(base_key=base_key,key=key)
                return ModelReply(**saved) if operation=='generate' else saved
            rows=db.execute('SELECT job_id,operation,day,reserved_tokens FROM provider_calls').fetchall()
            for scope,callcap,tokencap,netcap in [(lambda r:r['job_id']==self.job['id'],limits.max_job_calls,limits.max_job_tokens,limits.max_job_network_calls),(lambda r:r['day']==day,limits.max_daily_calls,limits.max_daily_tokens,limits.max_daily_network_calls)]:
                selected=[r for r in rows if scope(r)]
                if (len(selected)>=callcap or sum(r['reserved_tokens'] for r in selected)+reserve>tokencap
                    or (network and sum(r['operation']!='generate' for r in selected)>=netcap)):
                    raise OnlineError('budget_exhausted','本轮调用预算已达到安全上限。',429)
            db.execute('INSERT INTO provider_calls(job_id,key,operation,state,day,reserved_tokens,output_bytes) VALUES(?,?,?,?,?,?,0)',(self.job['id'],key,operation,'sent',day,reserve))
            self._fresh_key=key
            from .worker import LEASE_SECONDS
            current['lease_until']=self.clock()+LEASE_SECONDS;self.store._write(db,current)
        # A failure from here may already have been billed. Keep the sent reservation.
        received=None
        def receive(envelope):
            nonlocal received
            received=envelope
            raw=canonical({'_envelope':envelope}).encode()
            if len(raw)>min(limits.max_file_bytes,4*1024*1024):raise OnlineError('response_too_large','供应商回执超过接收限制。')
            self.files.put(self.job['id'],asset,BytesIO(raw),limits)
            recovery=envelope.get('_transport_recovery') if isinstance(envelope,dict) else None
            if (isinstance(recovery,dict) and recovery.get('kind')=='IncompleteRead'
                and recovery.get('basis')=='complete_json_completion_and_usage'
                and type(recovery.get('received_bytes')) is int and 0<recovery['received_bytes']<=4*1024*1024):
                metadata={k:recovery[k] for k in ('kind','basis','received_bytes')}
                self.files.put(self.job['id'],'transport-'+key+'.json',BytesIO(canonical(metadata).encode()),limits)
            actual=envelope.get('usage',{}).get('total_tokens') if isinstance(envelope,dict) and isinstance(envelope.get('usage'),dict) else None
            if type(actual) is not int or not 0<=actual<=reserve:actual=reserve
            with self.store.transaction() as db:db.execute("UPDATE provider_calls SET state='receipt_received',reserved_tokens=?,output_bytes=? WHERE job_id=? AND key=?",(actual,len(raw),self.job['id'],key))
        try:
            options={'receipt':receive} if operation=='generate' and getattr(self.provider,'supports_receipt',False) else {}
            reply=getattr(self.provider,operation)(**arguments,**options)
        except DeepSeekError as error:
            if getattr(error,'transport_info',None):
                diagnostic=canonical(error.transport_info).encode()
                self.files.put(self.job['id'],'transport-'+key+'.json',BytesIO(diagnostic),limits)
                partial=getattr(error,'partial_response',None)
                if isinstance(partial,bytes) and 0<len(partial)<=min(limits.max_file_bytes,4*1024*1024):
                    self.files.put(self.job['id'],'partial-'+key+'.bin',BytesIO(partial),limits)
            detail=getattr(error,'provider_detail','')
            if isinstance(detail,str) and detail:
                # Vendor explanation of a rejected request, kept in the private task dir.
                self.files.put(self.job['id'],'provider-error-'+key+'.txt',BytesIO(detail.encode('utf-8')),limits)
                # Shape only (no prompt text): a rejected request must be reproducible.
                try:
                    shape=canonical(dict(operation=operation,arguments=_wire_shape(arguments))).encode()
                    self.files.put(self.job['id'],'provider-shape-'+key+'.json',BytesIO(shape),limits)
                except Exception:pass
            if error.code in KNOWN_ACCESS_ERRORS or (received is not None and error.code in KNOWN_RESPONSE_ERRORS):
                usage=received.get('usage',{}) if isinstance(received,dict) and isinstance(received.get('usage'),dict) else {}
                raw=canonical({'_known_error':error.code,'usage':usage,'_transport_envelope':received}).encode()
                self.files.put(self.job['id'],asset,BytesIO(raw),limits)
                actual=usage.get('total_tokens')
                if type(actual) is not int or not 0<=actual<=reserve:actual=reserve
                with self.store.transaction() as db:
                    db.execute("UPDATE provider_calls SET state='failed_known',reserved_tokens=?,output_bytes=? WHERE job_id=? AND key=?",(actual,len(raw),self.job['id'],key))
                error.response_received=True
            raise
        raw=canonical(asdict(reply) if operation=='generate' else reply).encode()
        if len(raw)>min(limits.max_file_bytes,4*1024*1024):raise OnlineError('response_too_large','模型响应超过接收限制。')
        if operation=='generate':
            usage=reply.usage
            actual=usage.get('total_tokens')
            if type(actual) is not int or actual<0:raise OnlineError('invalid_usage','供应商未返回有效用量，停止后续调用。')
            if actual>reserve:raise OnlineError('usage_exceeded_reservation','供应商用量超出预留，停止后续调用。')
        else:actual=0
        self.files.put(self.job['id'],asset,BytesIO(raw),limits)
        with self.store.transaction() as db:
            require_lease(db,self.store,self.job,self.clock())
            db.execute("UPDATE provider_calls SET state='received',reserved_tokens=?,output_bytes=? WHERE job_id=? AND key=?",(actual,len(raw),self.job['id'],key))
        self.store.audit(self.job['id'],dict(stage=self.phase,calls=1,total_tokens=actual,model=self.model,outcome='response_received'))
        if not network:self.last_generation=dict(base_key=base_key,key=key)
        return reply
