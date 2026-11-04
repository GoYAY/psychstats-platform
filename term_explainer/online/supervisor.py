"""Bound each whole job, including native PDF/font/figure code, in a child."""
import os,signal,subprocess,time
from .store import canonical,TERMINAL
from .worker import active_runtime,stop_runtime,LEASE_SECONDS

def _stop(process):
    if process.poll() is not None:return
    if os.name=='nt':
        subprocess.run(['taskkill.exe','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW,timeout=5)
    else:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
    if process.poll() is None:process.kill()
    process.wait(timeout=5)

def run_isolated(config,store,job,command):
    remaining=max(0,config.limits.max_task_seconds-active_runtime(job,store.clock()))
    options={'creationflags':subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP} if os.name=='nt' else {'start_new_session':True}
    process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,**options)
    payload=canonical({k:job[k] for k in ('id','owner_id','lease_token')}).encode();deadline=time.monotonic()+remaining;first=True;reason=None
    try:
        while True:
            try:process.communicate(input=payload if first else None,timeout=min(.15,max(.01,deadline-time.monotonic())));break
            except subprocess.TimeoutExpired:first=False
            with store.transaction() as db:
                current=store._get(db,job['owner_id'],job['id'])
                invite=db.execute('SELECT revoked,expires FROM invites WHERE id=?',(job['owner_id'],)).fetchone()
                if current['state']!='running' or current['lease_token']!=job['lease_token']:reason='inactive_job'
                elif invite is None or invite['revoked'] or invite['expires']<=store.clock():reason='invite_revoked'
                else:current['lease_until']=store.clock()+LEASE_SECONDS;store._write(db,current)
            if time.monotonic()>=deadline:reason='task_timeout'
            if reason:_stop(process);break
    finally:
        if process.poll() is None:_stop(process)
        if process.stdin:process.stdin.close()
    with store.transaction() as db:
        current=store._get(db,job['owner_id'],job['id'])
        if current['state']!='running' or current['lease_token']!=job['lease_token']:return current
        sent=db.execute("SELECT 1 FROM provider_calls WHERE job_id=? AND state='sent' LIMIT 1",(job['id'],)).fetchone()
        state='cancelled' if reason=='invite_revoked' else 'needs_reconciliation' if sent else 'failed'
        stop_runtime(current,store.clock())
        current.update(state=state,version=current['version']+1,updated_at=store.clock(),terminal_at=store.clock() if state in TERMINAL else None,lease_token=None,lease_until=None,progress={'error_code':reason or 'worker_stopped'})
        store._write(db,current);return current
