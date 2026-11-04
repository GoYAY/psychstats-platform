"""Durable single-worker leases. Never blindly replay an uncertain request."""
import json,re,secrets,time
from .config import OnlineError
from .diagnostics import describe_failure
import logging
_LOG = logging.getLogger("psychstats.beta")
from .store import TRANSITIONS,PATCH_FIELDS,TERMINAL
from ..deepseek import DeepSeekError

LEASE_SECONDS=360
_SAFE_CODE=re.compile(r'[a-zA-Z0-9_:./-]{1,128}')

def active_runtime(job,now):
    started=job.get('started_at')
    return job.get('active_seconds',0)+(max(0,now-started) if started is not None else 0)

def stop_runtime(job,now):
    job['active_seconds']=active_runtime(job,now);job['started_at']=None

def require_lease(db,store,job,now):
    current=store._get(db,job['owner_id'],job['id'])
    invite=db.execute('SELECT revoked,expires FROM invites WHERE id=?',(job['owner_id'],)).fetchone()
    if (current['state']!='running' or current['lease_token']!=job.get('lease_token')
        or not current.get('lease_until') or current['lease_until']<=now
        or invite is None or invite['revoked'] or invite['expires']<=now):
        raise OnlineError('inactive_job','任务已停止或执行租约失效。',409)
    return current

class Worker:
    def __init__(self,config,store,*,runner,clock=time.time):
        self.config=config;self.store=store;self.runner=runner;self.clock=clock
        with store.connection() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS provider_calls(job_id TEXT NOT NULL,key TEXT NOT NULL,operation TEXT NOT NULL,state TEXT NOT NULL,day TEXT NOT NULL,reserved_tokens INTEGER NOT NULL,output_bytes INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(job_id,key))''')

    def claim(self,*,job_id=None):
        now=self.clock()
        with self.store.transaction() as db:
            jobs=[json.loads(r['body']) for r in db.execute('SELECT body FROM jobs ORDER BY rowid')]
            # Targeted QA must not recover, lease or otherwise mutate unrelated work.
            # Still honor the shared single-worker lease across the whole queue.
            if job_id is not None:
                if any(j['state']=='running' and (j.get('lease_until') or 0)>now for j in jobs):return None
                jobs=[j for j in jobs if j['id']==job_id]
            live=False
            for job in jobs:
                if job['state']!='running':continue
                if job.get('lease_until',0)>now:live=True;continue
                # The response file is atomically written before the receipt row.
                # Recover that narrow crash window without another external send.
                from .files import PrivateFiles
                files=PrivateFiles(self.config.private_root/'tasks')
                for call in db.execute("SELECT * FROM provider_calls WHERE job_id=? AND state='sent'",(job['id'],)).fetchall():
                    try:
                        receipt=json.loads(files.path_for(job['id'],'response-'+call['key']+'.json').read_bytes())
                        from .provider import KNOWN_ACCESS_ERRORS
                        if isinstance(receipt,dict) and receipt.get('_known_error') in KNOWN_ACCESS_ERRORS:
                            db.execute("UPDATE provider_calls SET state='failed_known' WHERE job_id=? AND key=?",(job['id'],call['key']));continue
                        if call['operation']=='generate':
                            from ..deepseek import ModelReply
                            reply=ModelReply(**receipt);usage=reply.usage.get('total_tokens')
                            if type(usage) is not int or not 0<=usage<=call['reserved_tokens']:continue
                        else:usage=0
                        db.execute("UPDATE provider_calls SET state='received',reserved_tokens=? WHERE job_id=? AND key=?",(usage,job['id'],call['key']))
                    except (OSError,ValueError,TypeError,OnlineError):pass
                sent=db.execute("SELECT 1 FROM provider_calls WHERE job_id=? AND state='sent' LIMIT 1",(job['id'],)).fetchone()
                stop_runtime(job,min(now,job.get('lease_until') or now))
                job.update(state='needs_reconciliation' if sent else 'queued',lease_token=None,lease_until=None,version=job['version']+1)
                self.store._write(db,job)
            if live:return None
            for job in jobs:
                if job['state']!='queued':continue
                invite=db.execute('SELECT revoked,expires FROM invites WHERE id=?',(job['owner_id'],)).fetchone()
                if invite is None or invite['revoked'] or invite['expires']<=now:continue
                job.update(state='running',lease_token=secrets.token_hex(32),lease_until=now+LEASE_SECONDS,version=job['version']+1,updated_at=now,started_at=now)
                self.store._write(db,job);return job
        return None

    def publish(self,claim,state,patch):
        if set(patch)-PATCH_FIELDS:raise OnlineError('invalid_patch','任务更新字段无效。')
        with self.store.transaction() as db:
            job=require_lease(db,self.store,claim,self.clock())
            if state!='running' and state not in TRANSITIONS['running']:raise OnlineError('invalid_transition','执行状态无效。')
            job.update(patch);job.update(state=state,version=job['version']+1,updated_at=self.clock(),lease_until=self.clock()+LEASE_SECONDS)
            if state!='running':stop_runtime(job,self.clock())
            if state in TERMINAL:job.update(terminal_at=self.clock(),lease_token=None,lease_until=None)
            elif state!='running':job.update(lease_token=None,lease_until=None)
            self.store._write(db,job);return job

    def tick(self,now=None):
        claim=self.claim()
        if claim is None:return None
        return self.execute(claim)

    def execute(self,claim):
        try:return self.runner(claim)
        except Exception as error:
            # A revoked invitation cannot pass publish's live authorization check.
            # Finalize only our still-owned lease, never a new worker's lease.
            with self.store.transaction() as db:
                fresh=self.store._get(db,claim['owner_id'],claim['id'])
                if fresh['state']!='running' or fresh['lease_token']!=claim['lease_token']:return fresh
                invite=db.execute('SELECT revoked,expires FROM invites WHERE id=?',(claim['owner_id'],)).fetchone()
                revoked=invite is None or invite['revoked'] or invite['expires']<=self.clock()
                from .provider import TRANSIENT_HTTP_ERRORS
                sent=db.execute("SELECT 1 FROM provider_calls WHERE job_id=? AND state='sent' LIMIT 1",(claim['id'],)).fetchone()
                raw=getattr(error,'code','') or ''
                # An HTTP error status is a confirmed non-delivery: the reservation is
                # already released, so this is a plain failure (resumable), not a call
                # that needs a human to reconcile a maybe-billed request.
                confirmed=getattr(error,'response_received',False) or raw in TRANSIENT_HTTP_ERRORS
                uncertain=(isinstance(error,DeepSeekError) and not confirmed) or bool(sent) or raw=='needs_reconciliation'
                state='cancelled' if revoked else 'needs_reconciliation' if uncertain else 'failed'
                code,diagnostics=describe_failure(error,stage=fresh.get('stage'))
                from .recovery import RECOVERABLE,MAX_RESUMES
                checkpoint=fresh.get('checkpoint') or {}
                target=getattr(error,'recovery_target',None)
                if isinstance(target,dict):checkpoint['recovery_target']=target
                counters=getattr(error,'reference_repair',None)
                if isinstance(counters,dict):checkpoint['reference_repair']=counters
                contract=getattr(error,'analysis_contract',None)
                if isinstance(contract,dict):checkpoint['analysis_contract_failure']=contract
                history=getattr(error,'analysis_contracts',None)
                if isinstance(history,list):checkpoint['analysis_contracts']=history
                fresh['checkpoint']=checkpoint
                repairable=bool(checkpoint.get('recovery_target')) or (code=='visual_review_required' and bool(checkpoint.get('visual_quality')))
                if state=='failed' and code in RECOVERABLE and repairable and checkpoint.get('recovery_resumes',0)<MAX_RESUMES:
                    state='waiting_input'
                    fresh['question']={'id':'recovery-'+secrets.token_hex(12),'kind':'recovery',
                        'messages':[diagnostics['public_message'],'修复问题后可从已保存进度继续；已有回执会复用，后续步骤可能新增模型调用。'],'candidates':[]}
                _LOG.warning('job %s failed type=%s stage=%s code=%s location=%s',
                    claim['id'],diagnostics['error_type'],diagnostics['stage'],code,diagnostics['location'])
                # Public codes hide vendor detail; keep the exact marker for diagnosis.
                # Written after this transaction closes: audit uses its own connection.
                trace=dict(error_code=raw,outcome='job_failed') if isinstance(raw,str) and _SAFE_CODE.fullmatch(raw) else None
                if trace is not None and isinstance(diagnostics.get('stage'),str) and _SAFE_CODE.fullmatch(diagnostics['stage']):
                    trace['stage']=diagnostics['stage']
                if trace is not None and isinstance(diagnostics.get('error_subcode'),str) and _SAFE_CODE.fullmatch(diagnostics['error_subcode']):
                    trace['error_subcode']=diagnostics['error_subcode']
                stop_runtime(fresh,self.clock())
                fresh.update(state=state,progress=dict(error_code=code,**diagnostics),terminal_at=self.clock() if state in TERMINAL else None,lease_token=None,lease_until=None,version=fresh['version']+1,updated_at=self.clock())
                self.store._write(db,fresh)
            if trace is not None:
                try:self.store.audit(claim['id'],trace)
                except Exception:pass
            return fresh
