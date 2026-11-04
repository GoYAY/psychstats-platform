"""One authorized supplied-text case, persisted in the existing shared ledger."""
from pathlib import Path
import argparse,hashlib,json,os,sys,subprocess
from dataclasses import asdict,replace
from io import BytesIO
from copy import deepcopy

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from rag.paths import basic_pdf
import tools.qa_online_generation_live as live
from term_explainer.contract import validate_request
from term_explainer.pipeline import prepare_evidence,generate_prepared_lesson,PipelineReply
from term_explainer.deepseek import DeepSeekClient
from term_explainer.online.store import OnlineStore
from term_explainer.online.worker import Worker
from term_explainer.online.provider import BudgetedProvider
from term_explainer.online.files import PrivateFiles
from term_explainer.online.delivery import build_delivery

CAPS=dict(model=110,network=10,tokens=1814277)
HOST=dict(interactive_chart_types=['bar'])
RUN=ROOT/'.superpowers/sdd/2026-10-23-shared-instant-chart-integration'
TEXTBOOK=basic_pdf()

def require_supported_bar(lesson):
    # Reuse the exact browser adapter rather than approximate its bounds in Python.
    module=(ROOT/'site/assets/charts/data.mjs').as_uri()
    script='import {personalBarData} from '+json.dumps(module)+';let s="";for await(const x of process.stdin)s+=x;process.exit(personalBarData(JSON.parse(s).visual)?0:1);'
    result=subprocess.run(['node','--input-type=module','-e',script],input=json.dumps(lesson,ensure_ascii=False),encoding='utf-8',capture_output=True,timeout=15)
    if result.returncode:raise ValueError('Final generated visual is not a supported interactive bar case')
    return lesson

def build_supported_delivery(job,request,lesson,sources,files,*,on_visual_repair=None,**kwargs):
    require_supported_bar(lesson)
    def corrected(repaired):
        require_supported_bar(repaired)
        if on_visual_repair:on_visual_repair(repaired)
    return build_delivery(job,request,lesson,sources,files,on_visual_repair=corrected,**kwargs)

def textbook_source():
    import pymupdf
    with pymupdf.open(TEXTBOOK) as doc:
        a,b,c,bar,axes=[doc[i].get_text() for i in (38,39,40,51,52)]
    parts=[a[a.index('第二节'):],b[:b.index('1.求全距')],c[c.index('4. 登记次数'):c.index('然后，取消')],bar[bar.index('(一)条形图'):],axes[:axes.index('第三，')]]
    text='\n\n'.join(parts)
    return dict(id='textbook-frequency',title='现代心理与教育统计学',scope='excerpt',origin='user',text=text,authors=[],year=None,doi='',url='',references=[]),dict(file=TEXTBOOK.name,pages_zero_based=[38,39,40,51,52],chapter='第二章 统计图表／次数分布表、条形图',excerpt_sha256=hashlib.sha256(text.encode()).hexdigest(),text_chars=len(text))

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');parser.add_argument('--resume-known-truncation',action='store_true');args=parser.parse_args()
    source,selection=textbook_source();config=live.configuration();config=replace(config,public_root=ROOT/'site/instant-chart-preview',limits=replace(config.limits,max_job_calls=8,max_daily_calls=110,max_job_tokens=300000,max_daily_tokens=CAPS['tokens'],max_output_tokens=32768))
    store=OnlineStore(live.RUN/'private/jobs.sqlite');files=PrivateFiles(config.private_root/'tasks')
    before=live.check_live_budget(store,caps=CAPS)
    print(json.dumps(dict(mode='execute' if args.execute else 'dry-run-no-requests',source=selection,budget_before=before,caps=CAPS,model_key_present=bool(os.environ.get('DEEPSEEK_API_KEY')),estimated_model_requests='2–5',estimated_tokens='20000–60000'),ensure_ascii=False),flush=True)
    if not args.execute:return
    with store.connection() as db:
        row=db.execute('SELECT id FROM invites WHERE revoked=0 AND expires>? ORDER BY created DESC LIMIT 1',(store.clock(),)).fetchone()
    if row is None:raise ValueError('No active existing test invitation; no model sent')
    request=dict(request_id='live-instant-frequency',term=dict(id='personal-frequency-distribution',zh='频数分布',en='Frequency Distribution',definition='',aliases=['次数分布']),question='拿到一份问卷，怎样看出各个选项有多少人选择？请用明确标注的教学数据绘制类别柱形图，帮助对照频数表理解人数分布，不做连续分箱图。',sources=[source],catalog=[],known_terms=[],literature_prompted=True,network_allowed=False,max_body_chars=2400,max_reference_reads=0)
    manifest=dict(kind='lesson',request=request,documents=[],model_allowed=True,network_allowed=False,source_selection=selection)
    key='live-instant-frequency-'+selection['excerpt_sha256'][:16];checkpoint={}
    if args.resume_known_truncation:
        with store.connection() as db:
            old_row=db.execute('SELECT body FROM jobs WHERE owner_id=? AND idem=?',(row['id'],key)).fetchone()
            if old_row is None:raise ValueError('No exact prior case')
            old=json.loads(old_row['body'])
            if old['manifest']!=manifest or old['state']!='failed' or old['progress'].get('error_code')!='model_truncated' or db.execute("SELECT 1 FROM provider_calls WHERE job_id=? AND state='sent'",(old['id'],)).fetchone():raise ValueError('Only exact known truncation can be explicitly resumed')
        checkpoint=deepcopy(old['checkpoint']);key+='-known-truncation-retry'
    job=store.create_job(row['id'],key,manifest,max_pending=10)
    if job['state']=='draft':job=store.enqueue(job['owner_id'],job['id'],job['version'],dict(checkpoint=checkpoint),max_queue=10)
    def runner(claim):
        provider=BudgetedProvider(config,store,files,claim,live.LiveExternal(store,DeepSeekClient(model='deepseek-flash',max_calls=8,max_tokens=32768,timeout=300),caps=CAPS))
        cp=dict(claim.get('checkpoint') or {});validated=validate_request(request)
        if 'prepared' not in cp:
            prepared=prepare_evidence(validated,provider);cp['prepared']=asdict(prepared);worker.publish(claim,'running',dict(stage='evidence',checkpoint=cp))
        else:prepared=PipelineReply(**cp['prepared'])
        if prepared.action!='ready_for_explanation':return worker.publish(claim,'waiting_input',dict(stage='evidence',question=dict(kind='scope',messages=prepared.questions),checkpoint=cp))
        if 'lesson' not in cp:
            result=generate_prepared_lesson(validated,provider,prepared,visual_host=HOST)
            if result.lesson is None or result.action!='complete':raise ValueError('No complete lesson; no success manufactured')
            cp['lesson']=asdict(result.lesson);worker.publish(claim,'running',dict(stage='rendering',checkpoint=cp))
        def corrected(lesson):cp['lesson']=lesson;worker.publish(claim,'running',dict(stage='rendering',checkpoint=cp))
        files.put(claim['id'],'supplied-excerpt.txt',BytesIO(source['text'].encode()),config.limits)
        artifact=build_supported_delivery(claim,request,cp['lesson'],prepared.evidence['sources'],files,originals={source['id']:files.path_for(claim['id'],'supplied-excerpt.txt')},qa_dir=config.figure_qa_dir,font_path=config.cjk_font,provider=provider,on_visual_repair=corrected,visual_host=HOST)
        return worker.publish(claim,'complete',dict(stage='ready',checkpoint=cp,result=artifact,usage=dict(calls=provider.calls)))
    worker=Worker(config,store,runner=runner)
    if job['state']=='queued':
        claim=worker.claim(job_id=job['id'])
        if claim is None or claim['id']!=job['id']:raise ValueError('Shared worker did not claim this selected case; stopped before any model request')
        job=worker.execute(claim)
    report=dict(job=job['id'],state=job['state'],progress=job['progress'],result=job.get('result'),source=selection,budget_before=before,budget_after=live.check_live_budget(store,caps=CAPS))
    RUN.mkdir(parents=True,exist_ok=True);(RUN/'frequency-live-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False),flush=True)
    if job['state']!='complete':raise SystemExit(1)

if __name__=='__main__':main()
