"""Authorized no-network continuation. Defaults to dry-run, shares old ledger."""
from copy import deepcopy
from dataclasses import asdict,replace
from pathlib import Path
import argparse,hashlib,json,os,sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import tools.qa_online_generation_live as live
from term_explainer.online.store import OnlineStore
from term_explainer.online.config import OnlineError
from term_explainer.online.worker import Worker
from term_explainer.online.provider import BudgetedProvider
from term_explainer.online.files import PrivateFiles
from term_explainer.online.delivery import build_delivery
from term_explainer.online.orchestrator import visual_host_for_config
from term_explainer.online.visual_repair import repair_visual
from term_explainer.online.visual_review import review_visual
from term_explainer.deepseek import DeepSeekClient
from term_explainer.contract import validate_request
from term_explainer.pipeline import PipelineReply,PipelineError,generate_prepared_lesson,_parse
from term_explainer.figures import validate_visual
from term_explainer.visual_presentation import validate_presentation

CAPS=dict(model=110,network=10,tokens=1814277)
OUT=ROOT/'logs/visual-intent-implementation-2026-10-24'
FREQUENCY='job-4e8daca5a66320648273784d690b4aab'
DRIFT='job-86e16cc4c9070fb5066d032ef8af5af5'

def phase_caps(calls,job_id):
    # Policy-file edits may produce a new idempotency key, never a fresh budget.
    other=[r for r in calls if r['job_id']!=job_id and r['diagnostic']=='visual-intent-v1']
    caps=dict(max_job_calls=12-sum(r['operation']=='generate' for r in other),max_job_tokens=250000-sum(r['reserved_tokens'] for r in other))
    if min(caps.values())<=0:raise OnlineError('budget_exhausted','本阶段跨版本调用额度已用完。',429)
    return caps

def bounded_visual(messages,provider,validate):
    messages=deepcopy(messages)
    for attempt in range(2):
        reply=provider.generate(messages)
        try:
            value=_parse(reply)
            if set(value)!={'visual'}:raise ValueError('Return only the visual field')
            validate(value['visual']);return value['visual']
        except (ValueError,PipelineError) as error:
            if attempt:raise ValueError('Single diagnostic structure repair exhausted') from error
            messages.extend([dict(role='assistant',content=reply.content),dict(role='user',content='仅修正JSON结构，严格只输出 {"visual":...}，保留已有数据和呈现选择；移除多余闭合括号及其他教学模块。问题：'+str(error))])

def control_review(request,lesson,sources,provider):
    # A control's protocol failure is a benchmark result, NOT a successful
    # review. Preserve it and continue the other controls without paid retries.
    try:return dict(protocol_status='valid',**review_visual(request,lesson,sources,provider))
    except (ValueError,PipelineError) as error:return dict(protocol_status='invalid',error=str(error))

def resume_known_validation(job,store):
    """Explicit QA-only recovery; retain original job, receipts and allowances."""
    with store.transaction() as db:
        fresh=store._get(db,job['owner_id'],job['id'])
        if fresh['state']!='failed' or fresh['manifest'].get('diagnostic')!='visual-intent-v1' or fresh.get('progress',{}).get('error_code')!='job_failed' or not {'frequency_delivery','drift_delivery','drift_lesson'}<=set(fresh.get('checkpoint',{})):raise ValueError('Not the exact known diagnostic failure')
        rows=db.execute('SELECT state FROM provider_calls WHERE job_id=?',(job['id'],)).fetchall()
        if not rows or any(r['state']!='received' for r in rows):raise ValueError('All prior sends must have known saved responses')
        cp=fresh['checkpoint'];cp.setdefault('qa_recoveries',[]).append(dict(reason='known_diagnostic_validation_recovery_with_received_receipts',prior_version=fresh['version']))
        # Archive the incomplete local export descriptor; rebuild it without API.
        if 'drift_delivery' in cp and 'drift_delivery_incomplete_archive' not in cp:cp['drift_delivery_incomplete_archive']=cp.pop('drift_delivery')
        fresh.update(state='queued',terminal_at=None,lease_token=None,lease_until=None,version=fresh['version']+1,progress={},checkpoint=cp)
        store._write(db,fresh);return fresh

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--resume-known-validation',action='store_true');a=p.parse_args()
    config=live.configuration();config=replace(config,public_root=ROOT/'site/visual-intent-preview',visual_intent_enabled=True,limits=replace(config.limits,max_job_calls=12,max_daily_calls=110,max_job_tokens=250000,max_daily_tokens=CAPS['tokens'],max_output_tokens=16384,max_job_network_calls=1))
    store=OnlineStore(live.RUN/'private/jobs.sqlite');files=PrivateFiles(config.private_root/'tasks');before=live.check_live_budget(store,caps=CAPS)
    with store.connection() as db:
        parents={key:json.loads(db.execute('SELECT body FROM jobs WHERE id=?',(jid,)).fetchone()['body']) for key,jid in [('frequency',FREQUENCY),('drift',DRIFT)]}
        owner=db.execute('SELECT id FROM invites WHERE revoked=0 AND expires>? ORDER BY created DESC LIMIT 1',(store.clock(),)).fetchone()
    host=visual_host_for_config(config)
    if host is None:raise ValueError('New verified candidate host required before live tests')
    hashes={name:hashlib.sha256((ROOT/'term_explainer/skills/explain-research-term'/name).read_bytes()).hexdigest() for name in ['SKILL.md','references/lesson-contract.md','references/instant-visuals.md','references/visual-review.md']}
    manifest=dict(kind='lesson',model_allowed=True,network_allowed=False,diagnostic='visual-intent-v1',parents=[FREQUENCY,DRIFT],policy_hashes=hashes,host=host)
    identity=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()[:20]
    report=dict(mode='execute' if a.execute else 'dry-run-no-requests',key_present=bool(os.environ.get('DEEPSEEK_API_KEY')),budget_before=before,max_new_requests=12,max_accounted_tokens=250000,new_network=0,pdf_rereads=0,host=host,input_hash=identity,frequency_chars=len(parents['frequency']['checkpoint']['prepared']['evidence']['sources'][0]['text']),expected_requests='8–12 including bounded repair; unused cases stop at original caps')
    print(json.dumps(report,ensure_ascii=False),flush=True)
    if not a.execute:return
    if owner is None:raise ValueError('Existing active test invite required')
    job=store.create_job(owner['id'],'visual-intent-'+identity,manifest,max_pending=10)
    if a.resume_known_validation:job=resume_known_validation(job,store)
    if job['state']=='draft':job=store.enqueue(job['owner_id'],job['id'],job['version'],dict(checkpoint=dict(budget_start=before,checks=[])),max_queue=10)
    def runner(claim):
        # Recompute AFTER the single-worker claim, so another completed policy
        # variant cannot be missed between dry-run and this execution.
        with store.connection() as db:
            calls=[dict(job_id=r['job_id'],operation=r['operation'],reserved_tokens=r['reserved_tokens'],diagnostic=json.loads(r['body'])['manifest'].get('diagnostic')) for r in db.execute('SELECT p.job_id,p.operation,p.reserved_tokens,j.body FROM provider_calls p JOIN jobs j ON p.job_id=j.id')]
        bounded_config=replace(config,limits=replace(config.limits,**phase_caps(calls,claim['id'])))
        provider=BudgetedProvider(bounded_config,store,files,claim,live.LiveExternal(store,DeepSeekClient(model='deepseek-flash',max_calls=12,max_tokens=16384,timeout=300),caps=CAPS));cp=deepcopy(claim['checkpoint'])
        def save(**changes):cp.update(changes);worker.publish(claim,'running',dict(stage='rendering',checkpoint=cp))
        def once(name,fn):
            if name in cp:return cp[name]
            value=fn();save(**{name:value});print(json.dumps(dict(step=name,calls=provider.calls),ensure_ascii=False),flush=True);return value
        # Actual complete teaching compilation using the already prepared source.
        parent=parents['frequency'];request=deepcopy(parent['manifest']['request']);request['question']+=' 本轮教学示例固定为120份问卷：非常不满意12人、不满意23人、满意68人、非常满意17人。须保留这些原始类别、人数与顺序。';prepared=PipelineReply(**deepcopy(parent['checkpoint']['prepared']));sources=prepared.evidence['sources']
        def compile_frequency():
            reply=generate_prepared_lesson(validate_request(dict(request,sources=sources)),provider,prepared,visual_host=host,visual_policy_version=1)
            if reply.lesson is None or reply.action!='complete':raise ValueError('No complete new frequency lesson')
            lesson=asdict(reply.lesson);v=lesson['visual'];validate_presentation(v,required=True)
            if v['payload'].get('chart_type')!='bar' or v['payload']['series'][0].get('y')!=[12,23,68,17] or v['payload']['series'][0].get('x')!=['非常不满意','不满意','满意','非常满意']:raise ValueError('Teaching benchmark data changed')
            return lesson
        freq=once('frequency_lesson',compile_frequency)
        once('frequency_delivery',lambda:build_delivery(dict(id=claim['id']+'-frequency'),request,freq,sources,files,qa_dir=config.figure_qa_dir,font_path=config.cjk_font,provider=provider,visual_host=host,quality_state=cp.get('frequency_quality'),on_quality_checkpoint=lambda value:save(frequency_quality=value)))
        # Adapt the accepted concrete feedback example through the real repair
        # contract, then execute mechanical and independent semantic gates.
        decision=parents['drift']['checkpoint']['decision'];request_d=decision['request'];sources_d=decision['sources'];old=parents['drift']['checkpoint']['lesson']
        drift=once('drift_lesson',lambda:repair_visual(request_d,old,sources_d,provider,visual_host=host,visual_policy_version=1,issues=['适配新版呈现合同；保留既有具体候选对象和跨轮依据传递，让图示与通俗解释互补。']))
        combined=deepcopy(sources_d);originals={}
        for doc,descriptor in zip(parents['drift']['checkpoint']['documents'],parents['drift']['manifest']['documents']):
            if doc['source']['id'] not in {s['id'] for s in combined}:combined.append(doc['source'])
            originals[doc['source']['id']]=files.path_for(DRIFT,descriptor['asset_id'])
        old_zip=files.path_for(claim['id']+'-drift','lesson.zip');preserved=files.path_for(claim['id']+'-drift','lesson-without-original-record.zip')
        if 'drift_delivery_incomplete_archive' in cp and old_zip.is_file() and not preserved.exists():old_zip.rename(preserved)
        once('drift_delivery',lambda:build_delivery(dict(id=claim['id']+'-drift'),request_d,drift,combined,files,originals=originals,qa_dir=config.figure_qa_dir,font_path=config.cjk_font,provider=provider,visual_host=host,quality_state=cp.get('drift_quality'),on_quality_checkpoint=lambda value:save(drift_quality=value)))
        # Independent whole-distribution intent generation, not diagnostic prose.
        from tests.term_explainer.test_statistical_presentation import classroom
        classroom_visual=classroom()
        def generate_whole():
            skill=ROOT/'term_explainer/skills/explain-research-term'
            prompt='\n\n'.join((skill/x).read_text(encoding='utf-8') for x in ['SKILL.md','references/lesson-contract.md','references/instant-visuals.md'])+'\n本次仅输出JSON {"visual":...}。只生成整体分布教学图，保留输入数据，不生成正文。'
            context=dict(term=dict(zh='集中趋势与离散程度',definition='中心位置与观测值的分散程度。'),question='两个班整体成绩分布有什么区别？',teaching_data=classroom_visual['payload'],generation_requirements=dict(visual_policy_version=1),visual_host=host)
            def check(v):validate_visual(v);validate_presentation(v,required=True)
            v=bounded_visual([dict(role='system',content=prompt),dict(role='user',content=json.dumps(context,ensure_ascii=False))],provider,check)
            # Scores are categorical labels here, not model inputs for arithmetic.
            # Compare their display value, retaining the raw received types.
            if [(list(map(str,s.get('x',[]))),s.get('y')) for s in v['payload'].get('series',[])]!=[(list(map(str,s['x'])),s['y']) for s in classroom_visual['payload']['series']]:raise ValueError('Whole-distribution input changed')
            return v
        once('whole_visual',generate_whole)
        # Trigger and normal controls are synthetic QA, not claimed research.
        for name,lesson in [('concrete-feedback',deepcopy(old)),('generic-labels',deepcopy(old))]:
            lesson['visual']['presentation']=dict(version=1,focus='process',numeric_role='none',layout='story',interaction='none')
            if name=='generic-labels':lesson['visual']['payload']=dict(layout='scenes',ordered=True,scenes=[dict(title='更确定',objects=[dict(id='one',kind='person',label='信心上升',state='selected')],connections=[]),dict(title='核查',objects=[dict(id='two',kind='record',label='查原文',state='neutral')],connections=[])])
            once('review_'+name,lambda lesson=lesson:control_review(request_d,lesson,sources_d,provider))
        from tests.term_explainer.helpers import request_payload,result_payload
        for name,per_category in [('whole-grouped',False),('category-grouped',True)]:
            r=request_payload();l=result_payload();r['sources']=[]
            r['term']=dict(id='teaching-control',zh='集中趋势与离散程度' if not per_category else '频数对比',en='',aliases=[],definition='数据中心与分散程度' if not per_category else '比较每个类别的实际人数')
            l['term']=r['term'];l['visual']=deepcopy(classroom_visual);l['visual']['presentation'].update(layout='grouped')
            if per_category:
                l['visual']['payload']['series']=[dict(label='甲组',x=['满意','不满意'],y=[68,32]),dict(label='乙组',x=['满意','不满意'],y=[50,50])];l['visual'].update(title='各组逐选项人数',takeaway='逐类别对照两组人数。',learning_goal='比较每个问卷选项中两组人数的差值。',adds_beyond_prose='按选项并排的实际人数。');l['visual']['presentation']['numeric_role']='exact'
            else:l['visual'].update(learning_goal='同时看到每班完整分布的中心和集中程度。',adds_beyond_prose='两班完整分布的形状。')
            for block in l['blocks']:
                for paragraph in block['paragraphs']:paragraph.update(text=r['term']['definition'],refs=[])
            once('review_'+name,lambda r=r,l=l:control_review(r,l,[],provider))
        return worker.publish(claim,'complete',dict(stage='ready',checkpoint=cp,usage=dict(calls=provider.calls)))
    worker=Worker(config,store,runner=runner)
    if job['state']=='queued':
        claim=worker.claim(job_id=job['id'])
        if claim is None:raise ValueError('Shared worker busy; no requests sent')
        job=worker.execute(claim)
    after=live.check_live_budget(store,caps=CAPS);cp=job['checkpoint'];report.update(job=job['id'],state=job['state'],progress=job['progress'],budget_start=cp.get('budget_start'),budget_after=after,steps=[k for k in cp if k not in ['frequency_lesson','drift_lesson','frequency_quality','drift_quality']],whole_policy=cp.get('whole_visual',{}).get('presentation'),reviews={k:v for k,v in cp.items() if k.startswith('review_')},private_deliveries={key:str(files.path_for(job['id']+'-'+key,'lesson.zip')) for key in ['frequency','drift'] if (key+'_delivery') in cp})
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'live-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False),flush=True)
    if job['state']!='complete':raise SystemExit(2)

if __name__=='__main__':main()
