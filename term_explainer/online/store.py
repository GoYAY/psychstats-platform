"""SQLite transactions shared by the HTTP process and one durable worker."""
from contextlib import contextmanager
from pathlib import Path
import hashlib,json,re,secrets,sqlite3,time
from .config import OnlineError

def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def identifier(prefix):return prefix+'-'+secrets.token_hex(16)
TERMINAL={'complete','failed','cancelled','expired'}
TRANSITIONS={
 'draft':{'queued','cancelled','expired'},
 'queued':{'running','cancelled','expired'},
 'running':{'waiting_input','needs_reconciliation','complete','failed','cancelled','expired','queued'},
 'waiting_input':{'queued','cancelled','expired'},
 'needs_reconciliation':{'queued','failed','cancelled','expired'},
}
PATCH_FIELDS={'stage','progress','question','result','usage','checkpoint','manifest','lease_token','lease_until'}

class OnlineStore:
    def __init__(self,path,*,clock=time.time):
        self.path=Path(path);self.clock=clock
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if self.path.is_symlink():raise OnlineError('invalid_config','数据库路径不安全。')
        with self.connection() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS invites(id TEXT PRIMARY KEY,hash TEXT UNIQUE NOT NULL,label TEXT NOT NULL,created REAL NOT NULL,expires REAL NOT NULL,revoked INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS sessions(hash TEXT PRIMARY KEY,invite_id TEXT NOT NULL REFERENCES invites(id),csrf TEXT NOT NULL,expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,idem TEXT NOT NULL,input_hash TEXT NOT NULL,body TEXT NOT NULL,UNIQUE(owner_id,idem));
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,job_id TEXT NOT NULL,at REAL NOT NULL,body TEXT NOT NULL);
            ''')

    @contextmanager
    def connection(self):
        db=sqlite3.connect(self.path,timeout=10,isolation_level=None);db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON');db.execute('PRAGMA busy_timeout=10000')
        try:yield db
        finally:db.close()

    @contextmanager
    def transaction(self):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:yield db;db.commit()
            except BaseException:db.rollback();raise

    def _get(self,db,owner_id,job_id):
        row=db.execute('SELECT body FROM jobs WHERE id=? AND owner_id=?',(job_id,owner_id)).fetchone()
        if row is None:raise OnlineError('not_found','任务不存在或无权访问。',404)
        return json.loads(row['body'])

    def _write(self,db,job):
        db.execute('UPDATE jobs SET body=? WHERE id=? AND owner_id=?',(canonical(job),job['id'],job['owner_id']))

    def create_job(self,owner_id,key,manifest,*,max_pending=None):
        if not isinstance(owner_id,str) or not owner_id or not isinstance(key,str) or not 1<=len(key)<=128:
            raise OnlineError('invalid_request','任务身份或幂等键无效。')
        if not isinstance(manifest,dict) or manifest.get('kind') not in {'lesson','organize'}:
            raise OnlineError('invalid_request','任务类型无效。')
        fingerprint=digest(manifest)
        with self.transaction() as db:
            old=db.execute('SELECT body,input_hash FROM jobs WHERE owner_id=? AND idem=?',(owner_id,key)).fetchone()
            if old:
                if old['input_hash']!=fingerprint:raise OnlineError('idempotency_conflict','提交标识已经用于其他输入。',409)
                return json.loads(old['body'])
            if max_pending is not None:
                pending=sum(json.loads(r['body'])['state'] not in TERMINAL for r in db.execute('SELECT body FROM jobs'))
                if pending>=max_pending:raise OnlineError('queue_full','测试任务已满，请完成或取消已有任务。',429)
            now=self.clock();job=dict(id=identifier('job'),owner_id=owner_id,kind=manifest['kind'],state='draft',stage='input',version=1,created_at=now,updated_at=now,terminal_at=None,manifest=manifest,progress=None,question=None,result=None,usage={},checkpoint=None,lease_token=None,lease_until=None)
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?)',(job['id'],owner_id,key,fingerprint,canonical(job)))
            return job

    def get_job(self,owner_id,job_id):
        with self.connection() as db:return self._get(db,owner_id,job_id)

    def enqueue(self,owner_id,job_id,expected_version,patch,*,max_queue):
        if set(patch)-PATCH_FIELDS:raise OnlineError('invalid_patch','任务更新字段无效。')
        with self.transaction() as db:
            job=self._get(db,owner_id,job_id)
            if type(expected_version) is not int or job['version']!=expected_version or job['state'] not in {'draft','waiting_input'}:raise OnlineError('stale_version','任务已更新。',409)
            pending=sum(json.loads(r['body'])['state'] in {'queued','running'} for r in db.execute('SELECT body FROM jobs'))
            if pending>=max_queue:raise OnlineError('queue_full','测试队列已满，请稍后继续。',429)
            job.update(patch);job.update(state='queued',version=job['version']+1,updated_at=self.clock())
            self._write(db,job);return job

    def list_jobs(self,owner_id):
        with self.connection() as db:
            return [json.loads(r['body']) for r in db.execute('SELECT body FROM jobs WHERE owner_id=? ORDER BY rowid DESC',(owner_id,))]

    def job_usage(self,job_id,*,files=None):
        with self.connection() as db:
            rows=db.execute('SELECT key,state,operation,reserved_tokens FROM provider_calls WHERE job_id=?',(job_id,)).fetchall()
        confirmed=pending=unconfirmed=0
        for row in rows:
            if row['state']=='received':confirmed+=row['reserved_tokens'];continue
            actual=None
            if row['state']=='failed_known' and files:
                try:
                    receipt=json.loads(files.path_for(job_id,'response-'+row['key']+'.json').read_bytes())
                    usage=receipt.get('usage',{}).get('total_tokens')
                    if type(usage) is int and 0<=usage<=row['reserved_tokens']:actual=usage
                except (OSError,ValueError,TypeError,AttributeError):pass
            if actual is not None:confirmed+=actual
            else:pending+=row['reserved_tokens'];unconfirmed+=1
        return dict(calls=len(rows),confirmed_tokens=confirmed,pending_reserved_tokens=pending,unconfirmed_calls=unconfirmed)

    def transition(self,owner_id,job_id,expected_version,state,patch):
        if not isinstance(patch,dict) or set(patch)-PATCH_FIELDS:raise OnlineError('invalid_patch','任务更新字段无效。')
        with self.transaction() as db:
            job=self._get(db,owner_id,job_id)
            if type(expected_version) is not int or job['version']!=expected_version:raise OnlineError('stale_version','任务已更新，请重新读取。',409)
            if job['state'] in TERMINAL or (state!=job['state'] and state not in TRANSITIONS.get(job['state'],set())):
                raise OnlineError('invalid_transition','任务状态不允许此操作。',409)
            job.update(patch);job.update(state=state,version=job['version']+1,updated_at=self.clock())
            if state in TERMINAL:job['terminal_at']=self.clock();job['lease_token']=None;job['lease_until']=None
            self._write(db,job);return job

    def audit(self,job_id,values):
        allowed={'stage','calls','model','total_tokens','prompt_tokens','completion_tokens','error_code','elapsed_ms','outcome'}
        if not isinstance(values,dict) or set(values)-allowed:raise OnlineError('unsafe_audit','审计字段不得含原文或凭证。')
        for key,value in values.items():
            if key in {'stage','model','error_code','outcome'}:
                if not isinstance(value,str) or not re.fullmatch(r'[a-zA-Z0-9_:./-]{1,128}',value):raise OnlineError('unsafe_audit','审计标记无效。')
            elif type(value) not in (int,float) or value<0:raise OnlineError('unsafe_audit','审计计数无效。')
        with self.transaction() as db:db.execute('INSERT INTO audit(job_id,at,body) VALUES(?,?,?)',(job_id,self.clock(),canonical(values)))
