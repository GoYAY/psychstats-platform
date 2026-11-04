"""Isolated HTTPS release harness; offline by default, explicit --live required."""
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
import argparse,json,os,sys,threading,time
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import tools.qa_online_generation_live as old
from tools.qa_online_generation_server import certificate
from tools.qa_release_budget import authorize_phase,check_phase,PhaseExternal
from term_explainer.online.store import OnlineStore
from term_explainer.online.config import load_config
from term_explainer.online.auth import InviteAuth
from term_explainer.online.files import PrivateFiles
from term_explainer.online.worker import Worker
from term_explainer.online.provider import BudgetedProvider
from term_explainer.online.orchestrator import advance_job,visual_host_for_config
from term_explainer.online.render_setup import check_renderer
from term_explainer.deepseek import DeepSeekClient

RUN=ROOT/'.superpowers/sdd/2026-10-24-online-release-readiness'

def queued_ids(store,owner):
    return [j['id'] for j in reversed(store.list_jobs(owner)) if j['state']=='queued']

def offline_transport(url,payload,headers,timeout):
    from tests.term_explainer.helpers import result_payload
    from tests.term_explainer.test_pipeline import analysis_payload
    if not url.endswith('/chat/completions'):raise ValueError('Offline fixture forbids network')
    context=json.loads(payload['messages'][-1]['content']);system=payload['messages'][0]['content']
    if 'review_targets' in context:
        value=dict(decision='pass',reason='离线夹具对象完整。',object_paths=[context['review_targets'][0]['path']],refs=[])
    elif 'section_ids' in system and 'sections' in context:value=dict(section_ids=[s['section_id'] for s in context['sections'][:2]],reason='Actual IDs only')
    elif 'evidence_bundle' in context:
        value=result_payload();value['term']=context['term'];value['content_id']='lesson-'+context['term']['id']
        source=context['sources'][0];span=source['spans'][0];ref=dict(source_id=source['id'],start=span['start'],end=min(span['end'],span['start']+10))
        for b in value['blocks']:
            for p in b['paragraphs']:p['refs']=[dict(ref)]
        value['relations'][0]['refs']=[dict(ref)]
        value['visual']['presentation']=dict(version=1,focus='structure',numeric_role='none',layout='story',interaction='none')
    else:
        sources=context['sources'];value=analysis_payload(tuple(s['id'] for s in sources));value.update(rolling_summary='Offline fixture, not real model evidence.',key_conditions=[])
        for note in value['reading_notes']+value['synthesis']:
            s=next(s for s in sources if s['id']==note['source_id']);note['evidence']=[dict(source_id=s['id'],span_id=s['spans'][0]['id'])]
        for claim in value['claims']:claim['evidence']=[dict(source_id=sources[0]['id'],span_id=sources[0]['spans'][0]['id'])]
    return dict(model='offline-fixture-not-live',usage=dict(prompt_tokens=10,completion_tokens=20,total_tokens=30),choices=[dict(finish_reason='stop',message=dict(content=json.dumps(value,ensure_ascii=False)))])

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--live',action='store_true');p.add_argument('--port',type=int,default=8894);p.add_argument('--public-root',type=Path,default=ROOT/'site/online-release-preview');a=p.parse_args()
    mode='live' if a.live else 'offline';record=RUN/(mode+'-https');record.mkdir(parents=True,exist_ok=True)
    cfg=old.configuration();private=cfg.private_root if a.live else record/'private'
    cfg=replace(cfg,private_root=private,public_root=a.public_root.resolve(),origin='https://127.0.0.1:'+str(a.port),api_prefix='/psy-stats/api/term-explainer/',generation_enabled=True,visual_intent_enabled=True,limits=replace(cfg.limits,max_job_calls=26,max_daily_calls=200,max_job_tokens=400000,max_daily_tokens=2000000,max_output_tokens=32768,max_job_network_calls=6,max_daily_network_calls=20))
    check_renderer(cfg)
    if visual_host_for_config(cfg) is None:raise ValueError('Combined verified visual host required')
    store=OnlineStore(private/'jobs.sqlite');files=PrivateFiles(private/'tasks');Worker(cfg,store,runner=None)
    if a.live:
        if not os.environ.get('DEEPSEEK_API_KEY'):raise ValueError('Key not configured')
        authorize_phase(store);budget=check_phase(store);(record/'budget-before.json').write_text(json.dumps(budget,indent=2),encoding='utf-8')
    auth=InviteAuth(store,cfg);meta_file=record/'active.json'
    if meta_file.exists():metadata=json.loads(meta_file.read_bytes())
    else:
        secret=auth.create_invite('release-readiness-'+mode);owner=auth.exchange(secret).owner_id
        metadata=dict(origin=cfg.origin,invitation=secret,owner=owner,run=str(record),mode=mode);meta_file.write_text(json.dumps(metadata),encoding='utf-8')
    owner=metadata['owner']
    def runner(job):
        client=DeepSeekClient(model='deepseek-flash',max_calls=26,max_tokens=32768,timeout=300,**({} if a.live else dict(api_key='OFFLINE-PLACEHOLDER',transport=offline_transport)))
        external=PhaseExternal(store,client) if a.live else client
        result=advance_job(job,store,files,BudgetedProvider(cfg,store,files,job,external))
        if a.live:(record/'budget-current.json').write_text(json.dumps(check_phase(store),indent=2),encoding='utf-8')
        else:
            with store.connection() as db:rows=db.execute('SELECT p.operation FROM provider_calls p JOIN jobs j ON p.job_id=j.id WHERE j.owner_id=?',(owner,)).fetchall()
            (record/'events.json').write_text(json.dumps([dict(phase=r['operation'],supplier='offline-double') for r in rows]),encoding='utf-8')
        return result
    worker=Worker(cfg,store,runner=runner)
    def process():
        while True:
            for job_id in queued_ids(store,owner):
                claim=worker.claim(job_id=job_id)
                if claim:
                    result=worker.execute(claim)
                    (record/'last-job.json').write_text(json.dumps({k:result.get(k) for k in ['id','state','stage','progress','question','result']},ensure_ascii=False,indent=2),encoding='utf-8')
            time.sleep(.2)
    from term_explainer.online.api import create_app
    from starlette.applications import Starlette
    from starlette.routing import Mount
    from starlette.staticfiles import StaticFiles
    api=create_app(cfg,store,files,provider_enabled=True)
    if a.live:
        # QA shares the historical accounting DB. Never expire or clean another
        # phase's evidence during this test. Normal cleanup remains tested in
        # the isolated offline API and production cleanup unit/integration tests.
        @asynccontextmanager
        async def no_historical_cleanup(app):yield
        api.router.lifespan_context=no_historical_cleanup
    app=Starlette(routes=[Mount('/psy-stats/api/term-explainer',app=api),Mount('/psy-stats',app=StaticFiles(directory=cfg.public_root,html=True))])
    threading.Thread(target=process,daemon=True).start();key,cert=certificate(record)
    print(json.dumps(dict(url=cfg.origin+'/psy-stats/library/index.html#view=generate',mode=mode,externalCalls='authorized bounded live' if a.live else 0)),flush=True)
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=a.port,ssl_keyfile=str(key),ssl_certfile=str(cert),access_log=False,log_level='warning')

if __name__=='__main__':main()
