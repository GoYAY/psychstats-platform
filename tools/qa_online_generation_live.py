"""Development-only live validation. Importing this module sends no requests."""
from pathlib import Path
import argparse,json,sys,os,time,hashlib
from io import BytesIO
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from term_explainer.online.config import OnlineError

MAX_MODEL=80
MAX_NETWORK=12
MAX_TOKENS=2000000

def check_live_budget(store,*,caps=None):
    """Check all persisted reservations across dates, including the pending send."""
    with store.connection() as db:
        rows=db.execute('SELECT operation,state,reserved_tokens FROM provider_calls').fetchall()
        has_external=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='live_external_verifications'").fetchone()
        external=db.execute('SELECT COUNT(*) FROM live_external_verifications').fetchone()[0] if has_external else 0
    report=dict(modelRequests=sum(r['operation']=='generate' for r in rows),networkRequests=sum(r['operation']!='generate' for r in rows)+external,tokensAccounted=sum(r['reserved_tokens'] for r in rows),uncertainRequests=sum(r['state']=='sent' for r in rows))
    if caps is not None and (not isinstance(caps,dict) or set(caps)!={'model','network','tokens'} or any(type(caps[k]) is not int or not 0<caps[k]<=ceiling for k,ceiling in [('model',110),('network',10),('tokens',1814277)])):raise ValueError('Invalid explicit continuation budget')
    model,network,tokens=(caps['model'],caps['network'],caps['tokens']) if caps is not None else (MAX_MODEL,MAX_NETWORK,MAX_TOKENS)
    if report['modelRequests']>model or report['networkRequests']>network or report['tokensAccounted']>tokens:
        raise OnlineError('live_budget_exhausted','本轮合计预算已达到上限，未继续发送。',429)
    return report

class LiveExternal:
    supports_receipt=True
    def __init__(self,store,client,*,caps=None):self.store=store;self.client=client;self.model=client.model;self.caps=caps
    def generate(self,**kwargs):check_live_budget(self.store,caps=self.caps);return self.client.generate(**kwargs)
    def search(self,**kwargs):check_live_budget(self.store,caps=self.caps);return self.client.search(**kwargs)
    def fetch(self,**kwargs):check_live_budget(self.store,caps=self.caps);return self.client.fetch(**kwargs)

class InheritedReplies:
    """Explicit test-only replay of exact same-owner received requests."""
    def __init__(self,provider,parents):self.provider=provider;self.parents=parents
    def __getattr__(self,name):return getattr(self.provider,name)
    def generate(self,messages,*args,**kwargs):
        from term_explainer.online.store import digest
        from term_explainer.online.worker import require_lease
        from term_explainer.deepseek import ModelReply
        key=digest(dict(operation='generate',arguments=dict(messages=messages,reasoning_effort=kwargs.get('reasoning_effort','high'))))
        with self.store.transaction() as db:
            require_lease(db,self.store,self.job,self.clock())
            for parent in self.parents:
                row=db.execute('SELECT body FROM jobs WHERE id=? AND owner_id=?',(parent,self.job['owner_id'])).fetchone()
                call=db.execute("SELECT 1 FROM provider_calls WHERE job_id=? AND key=? AND state='received'",(parent,key)).fetchone()
                if row and call:return ModelReply(**json.loads(self.files.path_for(parent,'response-'+key+'.json').read_bytes()))
        return self.provider.generate(messages,*args,**kwargs)

RUN=ROOT/'.superpowers/sdd/2026-10-22-online-generation-beta-implementation/live-validation'
from rag.paths import input_path
PAPERS={
 'drift':(input_path('PSY_STATS_DRIFT_PDF','data/papers/drift.pdf'),'Boosting Metacognition in Entangled Human–AI Interaction to Navigate Cognitive–Behavioral Drift'),
 'dtp':(input_path('PSY_STATS_DTP_PDF','data/papers/dtp.pdf'),'The Dominant Trait Profile Method of Scoring Multidimensional Forced-Choice Questionnaires'),
 'brown':(input_path('PSY_STATS_BROWN_PDF','data/papers/brown2011.pdf'),'Item Response Modeling of Forced-Choice Questionnaires'),
}
CASES={
 'no-literature':dict(zh='人–AI交互中的纠缠',en='Entanglement in Human–AI Interaction',question='理解持续人–AI交互中双方如何相互塑造后续判断与互动。',papers=[]),
 'single-branch':dict(zh='认知漂移',en='Cognitive drift',question='解释人–AI交互中的认知漂移，核对它在整体研究中的位置，不将整篇文章的框架等同于该概念。',papers=['drift']),
 'multi-literature':dict(zh='优势特质剖面计分法',en='Dominant Trait Profile',question='理解DTP的计分逻辑、用途及与既有强迫选择计分的关系，不生成R实操代码。',papers=['dtp','brown']),
}

def configuration():
    from term_explainer.online.config import load_config
    env=dict(os.environ)
    values=dict(PRIVATE_ROOT=str(RUN/'private'),PUBLIC_ROOT=str(ROOT/'site/online-generation-preview'),ORIGIN='https://127.0.0.1:8875',API_PREFIX='/psy-stats/api/term-explainer/',GENERATION_ENABLED='true',MAX_JOB_CALLS='80',MAX_DAILY_CALLS='92',MAX_JOB_TOKENS='1600000',MAX_DAILY_TOKENS=str(MAX_TOKENS),MAX_OUTPUT_TOKENS='32768',MAX_JOB_NETWORK_CALLS='12',MAX_DAILY_NETWORK_CALLS='12',MAX_FILE_BYTES='20000000',MAX_TOTAL_BYTES='40000000',MAX_FILES='3',MAX_PAGES='150',MAX_TEXT_CHARS='120000',MAX_TASK_SECONDS='7200',MAX_QUEUE='10',REQUEST_TIMEOUT='300')
    env.update({'TERM_'+k:v for k,v in values.items()})
    env.setdefault('TERM_FIGURE_QA_DIR',str(Path.home()/'.codex/skills/nature-figure/scripts'))
    env.setdefault('TERM_CJK_FONT','C:/Windows/Fonts/msyh.ttc')
    return load_config(env)

def resume_exact_identity_job(job,store):
    """Recover this test's interior-title pause only, keeping paid reading notes."""
    from copy import deepcopy
    from term_explainer.online.sources import exact_identity_review
    question=job.get('question') or {};messages=question.get('messages',[])
    if job['state']!='waiting_input' or question.get('kind')!='scope' or not messages or not all(m.startswith('取得页面与所给文献身份需要确认：') and any(w in m for w in ('未重印','未重复','not repeated')) for m in messages):raise OnlineError('manual_review_required','当前问题不是可精确核对的内页题名缺失。')
    checkpoint=deepcopy(job['checkpoint']);decision=checkpoint['decision']
    for doc in checkpoint['documents']:
        review=exact_identity_review(doc['source'])
        if review is None:raise OnlineError('manual_review_required','原件尚无可精确定位的完整题名。')
        doc['identity_review']=review;reading=decision['readings'].get(doc['source']['id'])
        if reading:
            if reading['source_hash']!=review['source_hash']:raise OnlineError('manual_review_required','原文指纹已改变。')
            reading['identity_review']=review
            if reading['status']=='needs_disambiguation':reading['status']='reading';reading.pop('questions',None)
    decision.update(action='input',question=None,version=decision['version']+1)
    checkpoint['identity_recovery']='local_exact_title_match_no_scientific_endorsement'
    return store.enqueue(job['owner_id'],job['id'],job['version'],dict(checkpoint=checkpoint,question=None),max_queue=10)

def run_case(name,config,store,files,owner,*,attempt='',clarify=None,resume_identity=False,reuse_failed=False,inherit_received=None):
    from term_explainer.online.worker import Worker
    from term_explainer.online.provider import BudgetedProvider
    from term_explainer.online.orchestrator import advance_job
    from term_explainer.online.sources import apply_answer
    from term_explainer.deepseek import DeepSeekClient
    case=CASES[name];docs=[]
    for i,key in enumerate(case['papers']):
        path,title=PAPERS[key];raw=path.read_bytes();sid='live-'+name+'-'+str(i)
        docs.append(dict(id=sid,name=path.name,title=title,mime='application/pdf',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),asset_id=sid+'.pdf',uploaded=True))
    request=dict(request_id='live-'+name,term=dict(id='live-term-'+name,zh=case['zh'],en=case['en'],definition='',aliases=[]),question=case['question'],sources=[],catalog=[],known_terms=[],literature_prompted=False,network_allowed=name=='no-literature',max_body_chars=4500)
    manifest=dict(kind='lesson',request=request,documents=docs,model_allowed=True,network_allowed=name=='no-literature')
    key='live-'+name+('-'+attempt if attempt else '')
    job=store.create_job(owner,key,manifest,max_pending=10)
    if job['state']=='draft':
        for descriptor,key in zip(docs,case['papers']):files.put(job['id'],descriptor['asset_id'],BytesIO(PAPERS[key][0].read_bytes()),config.limits)
        changes={}
        if inherit_received:
            from copy import deepcopy
            with store.connection() as db:
                row=db.execute('SELECT body FROM jobs WHERE owner_id=? AND idem=?',(owner,'live-'+name+'-'+inherit_received)).fetchone()
                if row is None:raise OnlineError('replay_mismatch','未找到指定的旧尝试。')
                old=json.loads(row['body'])
                uncertain=db.execute("SELECT 1 FROM provider_calls WHERE job_id=? AND state='sent'",(old['id'],)).fetchone()
            if old['state']!='failed' or old['manifest']!=manifest or uncertain:raise OnlineError('replay_mismatch','只能显式继承同输入且没有未知发送的失败测试。')
            checkpoint=deepcopy(old['checkpoint'])
            checkpoint['inherited_responses_from']=[old['id'],*checkpoint.get('inherited_responses_from',[])]
            if checkpoint['decision'].get('action')!='ready':checkpoint['decision'].update(action='input',question=None)
            changes={'checkpoint':checkpoint}
        if reuse_failed:
            # Explicit development recovery: old terminal job and charges stay
            # immutable; locally revalidate its last received section response.
            from copy import deepcopy
            from term_explainer.deepseek import ModelReply
            from term_explainer.section_reading import read_next_section
            with store.connection() as db:
                old=json.loads(db.execute('SELECT body FROM jobs WHERE owner_id=? AND idem=?',(owner,'live-'+name)).fetchone()['body'])
                if db.execute("SELECT 1 FROM provider_calls WHERE job_id=? AND state='sent'",(old['id'],)).fetchone():raise OnlineError('needs_reconciliation','旧任务尚有未确认请求，不能重放。')
                call=db.execute("SELECT * FROM provider_calls WHERE job_id=? AND operation='generate' AND state='received' ORDER BY rowid DESC LIMIT 1",(old['id'],)).fetchone()
            if old['state']!='failed' or old['stage']!='reading' or old['manifest']!=manifest or call is None:raise OnlineError('replay_mismatch','旧任务与选定材料不一致。')
            checkpoint=deepcopy(old['checkpoint']);decision=checkpoint['decision']
            readings=[r for r in decision['readings'].values() if r['status']=='failed_requires_review']
            if len(readings)!=1:raise OnlineError('replay_mismatch','不能确定需要重放的小节。')
            reading=readings[0];source=next(d['source'] for d in checkpoint['documents'] if d['source']['id']==reading['paper_id'])
            payload=json.loads(files.path_for(old['id'],'response-'+call['key']+'.json').read_bytes())
            class Replay:
                def generate(self,messages,*args,**kwargs):return ModelReply(**payload)
            before=reading['next_section'];reading['status']='reading';reading['reserved_calls']-=1
            read_next_section(reading,dict(decision['request'],network_allowed=True),source,Replay(),context_limit=64000)
            if reading['next_section']!=before+1:raise OnlineError('replay_not_accepted','已有响应仍需核对，未追加模型请求。')
            decision.update(action='input',question=None,version=decision['version']+1)
            checkpoint['inherited_reading']=dict(job_id=old['id'],response_key=call['key'],revalidated_locally=True,new_requests=0)
            changes={'checkpoint':checkpoint}
        job=store.enqueue(owner,job['id'],job['version'],changes,max_queue=10)
    if resume_identity:job=resume_exact_identity_job(job,store)
    if clarify and job['state']=='waiting_input':
        checkpoint=job['checkpoint'];decision=checkpoint['decision']
        checkpoint['decision']=apply_answer(decision,dict(question_id=decision['question']['id'],action='clarify',explanation=clarify),decision['version'])
        job=store.enqueue(owner,job['id'],job['version'],dict(checkpoint=checkpoint,question=None),max_queue=10)
    def execute(claim):
        raw=DeepSeekClient(model='deepseek-flash',max_calls=80,max_tokens=config.limits.max_output_tokens,timeout=config.limits.request_timeout)
        provider=BudgetedProvider(config,store,files,claim,LiveExternal(store,raw))
        parents=(claim.get('checkpoint') or {}).get('inherited_responses_from',[])
        return advance_job(claim,store,files,InheritedReplies(provider,parents) if parents else provider)
    worker=Worker(config,store,runner=execute)
    for _ in range(8):
        job=store.get_job(owner,job['id'])
        if job['state']=='queued':
            print(json.dumps(dict(case=name,state='running',budget=check_live_budget(store)),ensure_ascii=False),flush=True)
            worker.tick();continue
        if job['state']!='waiting_input':break
        decision=job['checkpoint']['decision'];q=decision['question'];answer=None
        if name=='no-literature' and q['kind']=='literature':answer=dict(question_id=q['id'],action='continue',allow_network=True)
        elif name=='no-literature' and q['kind']=='concept':
            from urllib.parse import urlsplit
            # Test-owned expected source, selected in advance from the supplied
            # paper's canonical arXiv identity. Unknown search hits are NOT chosen.
            matching=[c for c in q['candidates'] if urlsplit(c.get('url','')).hostname in ('arxiv.org','www.arxiv.org') and '2602.01959' in urlsplit(c.get('url','')).path]
            if len(matching)==1:answer=dict(question_id=q['id'],candidate_id=matching[0]['id'])
        if answer is None:break
        checkpoint=job['checkpoint'];checkpoint['decision']=apply_answer(decision,answer,decision['version'])
        changed=dict(job['manifest']);changed['network_allowed']=checkpoint['decision']['request']['network_allowed']
        store.enqueue(owner,job['id'],job['version'],dict(checkpoint=checkpoint,manifest=changed,question=None),max_queue=10)
    job=store.get_job(owner,job['id'])
    report=dict(case=name,id=job['id'],state=job['state'],stage=job['stage'],progress=job['progress'],question=job['question'],budget=check_live_budget(store),result=job['result'],elapsedSeconds=round(time.time()-job['created_at'],2),realProvider=True)
    (RUN/(name+('-'+attempt if attempt else '')+'-report.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    visible={**report,'question':{k:report['question'][k] for k in ('id','kind','messages')} if report['question'] else None}
    print(json.dumps(visible,ensure_ascii=False),flush=True);return report

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--case',choices=[*CASES,'all'],default='all');p.add_argument('--execute',action='store_true');p.add_argument('--attempt',default='');p.add_argument('--clarify');p.add_argument('--resume-exact-identity',action='store_true');p.add_argument('--reuse-failed-reading',action='store_true');p.add_argument('--inherit-received');args=p.parse_args(argv)
    if args.attempt and not __import__('re').fullmatch(r'[a-z0-9-]{1,30}',args.attempt):p.error('Invalid attempt label')
    if args.reuse_failed_reading and not args.attempt:p.error('An explicit new attempt label is required')
    if args.inherit_received and (not args.attempt or not __import__('re').fullmatch(r'[a-z0-9-]{1,30}',args.inherit_received)):p.error('Explicit valid attempt labels are required')
    selected=list(CASES) if args.case=='all' else [args.case]
    if not args.execute:
        print(json.dumps(dict(mode='dry-run-no-requests',cases=selected,materials={k:dict(name=v[0].name,available=v[0].is_file()) for k,v in PAPERS.items()},caps=dict(model=MAX_MODEL,network=MAX_NETWORK,tokens=MAX_TOKENS)),ensure_ascii=False,indent=2));return
    if not os.environ.get('DEEPSEEK_API_KEY'):raise SystemExit('API key not configured; no live request sent.')
    from term_explainer.online.store import OnlineStore
    from term_explainer.online.files import PrivateFiles
    from term_explainer.online.auth import InviteAuth
    from term_explainer.online.worker import Worker
    from term_explainer.online.render_setup import check_renderer
    config=configuration();check_renderer(config);RUN.mkdir(parents=True,exist_ok=True)
    store=OnlineStore(config.private_root/'jobs.sqlite');files=PrivateFiles(config.private_root/'tasks');Worker(config,store,runner=None)
    check_live_budget(store)
    with store.connection() as db:rows=db.execute("SELECT id FROM invites WHERE label='authorized-live-validation' AND revoked=0").fetchall()
    if rows:owner=rows[0]['id']
    else:
        auth=InviteAuth(store,config);secret=auth.create_invite('authorized-live-validation');owner=auth.exchange(secret).owner_id;del secret
    for name in selected:run_case(name,config,store,files,owner,attempt=args.attempt,clarify=args.clarify,resume_identity=args.resume_exact_identity,reuse_failed=args.reuse_failed_reading,inherit_received=args.inherit_received)

if __name__=='__main__':main()
