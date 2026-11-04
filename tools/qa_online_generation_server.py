"""Loopback HTTPS integration fixture. ALL supplier traffic is an offline double."""
import argparse,ipaddress,json,sys,threading,time,uuid
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tests.term_explainer.online.helpers import environment
from tests.term_explainer.helpers import result_payload
from tests.term_explainer.test_pipeline import analysis_payload
from term_explainer.online.config import load_config
from term_explainer.online.store import OnlineStore
from term_explainer.online.auth import InviteAuth
from term_explainer.online.files import PrivateFiles,cleanup_jobs
from term_explainer.online.worker import Worker
from term_explainer.online.provider import BudgetedProvider
from term_explainer.online.orchestrator import advance_job
from term_explainer.deepseek import DeepSeekClient

def certificate(folder):
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes,serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'isolated-loopback-qa')]);now=datetime.now(timezone.utc)
    cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(days=1)).add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False).sign(key,hashes.SHA256()))
    keyfile=folder/'test-key.pem';certfile=folder/'test-cert.pem'
    keyfile.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    certfile.write_bytes(cert.public_bytes(serialization.Encoding.PEM));return keyfile,certfile

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8874);args=parser.parse_args()
    base=ROOT/'.superpowers/sdd/2026-10-22-online-generation-beta-implementation/https-qa';folder=base/uuid.uuid4().hex;folder.mkdir(parents=True)
    env=environment(folder);env.update(TERM_PUBLIC_ROOT=str(ROOT/'site/online-generation-preview'),TERM_ORIGIN='https://127.0.0.1:'+str(args.port),TERM_API_PREFIX='/psy-stats/api/term-explainer/')
    config=load_config(env);store=OnlineStore(config.private_root/'jobs.sqlite');files=PrivateFiles(config.private_root/'tasks');auth=InviteAuth(store,config)
    secret=auth.create_invite('isolated-integration-fixture');events=[]
    metadata={'origin':config.origin,'invitation':secret,'run':str(folder),'externalCalls':0}
    (base/'active.json').write_text(json.dumps(metadata),encoding='utf-8')
    def transport(url,payload,headers,timeout):
        if not url.endswith('/chat/completions'):raise RuntimeError('Offline fixture forbids search/fetch traffic')
        context=json.loads(payload['messages'][-1]['content']);system=payload['messages'][0]['content']
        if 'section_ids' in system and 'sections' in context:
            result={'section_ids':[s['section_id'] for s in context['sections'][:2]],'reason':'Selected from actual section IDs.'}
            phase='selection'
        elif 'evidence_bundle' in context:
            result=result_payload();result['term']=context['term'];result['content_id']='lesson-'+context['term']['id']
            source=context['sources'][0];span=source['spans'][0];ref={'source_id':source['id'],'start':span['start'],'end':min(span['end'],span['start']+10)}
            for block in result['blocks']:
                for p in block['paragraphs']:p['refs']=[dict(ref)]
            result['relations'][0]['refs']=[dict(ref)];phase='lesson'
        else:
            sources=context.get('sources',[])
            if not sources:raise RuntimeError('Unexpected offline QA prompt shape')
            result=analysis_payload(tuple(s['id'] for s in sources));result.update(rolling_summary='Fixture reading memory, not real model evidence.',key_conditions=[])
            for note in result['reading_notes']+result['synthesis']:
                source=next(s for s in sources if s['id']==note['source_id']);note['evidence']=[{'source_id':source['id'],'span_id':source['spans'][0]['id']}]
            for claim in result['claims']:claim['evidence']=[{'source_id':sources[0]['id'],'span_id':sources[0]['spans'][0]['id']}]
            phase='analysis'
        events.append({'phase':phase});(folder/'events.json').write_text(json.dumps(events),encoding='utf-8')
        return {'model':'offline-fixture-not-live','usage':{'prompt_tokens':10,'completion_tokens':20,'total_tokens':30},'choices':[{'finish_reason':'stop','message':{'content':json.dumps(result,ensure_ascii=False)}}]}
    def run(job):
        client=DeepSeekClient(api_key='OFFLINE-PLACEHOLDER',max_calls=80,transport=transport)
        return advance_job(job,store,files,BudgetedProvider(config,store,files,job,client))
    worker=Worker(config,store,runner=run)
    def process():
        while True:worker.tick();time.sleep(.1)
    threading.Thread(target=process,daemon=True).start()
    from term_explainer.online.api import create_app
    from starlette.applications import Starlette
    from starlette.routing import Mount
    from starlette.staticfiles import StaticFiles
    api=create_app(config,store,files,provider_enabled=True)
    app=Starlette(routes=[Mount('/psy-stats/api/term-explainer',app=api),Mount('/psy-stats',app=StaticFiles(directory=config.public_root,html=True))])
    key,cert=certificate(folder)
    print(json.dumps({'url':config.origin+'/psy-stats/library/index.html#view=generate','fixture':'offline-supplier-only','externalCalls':0}),flush=True)
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=args.port,ssl_keyfile=str(key),ssl_certfile=str(cert),access_log=False,log_level='warning')

if __name__=='__main__':main()
