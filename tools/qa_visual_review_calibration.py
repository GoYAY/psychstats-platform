"""Three once-only review controls, same authorized phase; dry-run by default."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import argparse,hashlib,json,os,sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import tools.qa_online_generation_live as live
from tools.qa_visual_intent_live import CAPS,DRIFT,phase_caps,control_review
from term_explainer.online.store import OnlineStore
from term_explainer.online.worker import Worker
from term_explainer.online.provider import BudgetedProvider
from term_explainer.online.files import PrivateFiles
from term_explainer.deepseek import DeepSeekClient

OUT=ROOT/'logs/visual-review-calibration-2026-10-24'

def controls(parent):
    """Expected labels belong in the evaluator, not these model inputs."""
    decision=parent['checkpoint']['decision'];r=deepcopy(decision['request']);l=deepcopy(parent['checkpoint']['lesson'])
    l['visual']['presentation']=dict(version=1,focus='process',numeric_role='none',layout='story',interaction='none')
    cases=[('concrete-feedback',r,l,decision['sources'])]
    from tests.term_explainer.test_statistical_presentation import classroom
    from tests.term_explainer.helpers import request_payload,result_payload
    for name,category in [('whole-grouped',False),('category-grouped',True)]:
        r=request_payload();l=result_payload();r['sources']=[]
        r['term']=dict(id='teaching-control',zh='逐类别频数比较' if category else '集中趋势与离散程度',en='',aliases=[],definition='比较各类别的人数差异。' if category else '描述数据中心位置与分散程度。')
        r['question']='每个满意度选项，两组人数相差多少？' if category else '两班成绩的整体中心和集中程度有什么区别？请关注每班完整分布，而非各分数段人数的逐项比较。'
        l['term']=deepcopy(r['term']);l['visual']=classroom();v=l['visual'];v['presentation'].update(layout='grouped')
        if category:
            v['payload']['series']=[dict(label='甲组',x=['满意','不满意'],y=[68,32]),dict(label='乙组',x=['满意','不满意'],y=[50,50])]
            v['payload'].update(x_label='满意度选项',x_unit='')
            v.update(title='各组逐选项人数',alt='甲组与乙组在满意、不满意两项中的人数对照。',takeaway='逐类别对照两组人数。',learning_goal='比较每个问卷选项中两组人数的差值。',adds_beyond_prose='按选项并排的实际人数。')
            v['presentation'].update(focus='local',numeric_role='exact')
        else:v.update(learning_goal='同时看到每班完整分布的中心和集中程度。',adds_beyond_prose='两班完整分布的形状。')
        v['refs']=[]
        for b in l['blocks']:
            for p in b['paragraphs']:p.update(text=r['term']['definition'],refs=[])
        cases.append((name,r,l,[]))
    return cases

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    config=live.configuration();store=OnlineStore(live.RUN/'private/jobs.sqlite');files=PrivateFiles(config.private_root/'tasks')
    before=live.check_live_budget(store,caps=CAPS)
    with store.connection() as db:
        parent=json.loads(db.execute('SELECT body FROM jobs WHERE id=?',(DRIFT,)).fetchone()['body'])
        owner=db.execute('SELECT id FROM invites WHERE revoked=0 AND expires>? ORDER BY created DESC LIMIT 1',(store.clock(),)).fetchone()
        rows=[dict(job_id=r['job_id'],operation=r['operation'],reserved_tokens=r['reserved_tokens'],diagnostic=json.loads(r['body'])['manifest'].get('diagnostic')) for r in db.execute('SELECT p.job_id,p.operation,p.reserved_tokens,j.body FROM provider_calls p JOIN jobs j ON p.job_id=j.id')]
    cases=controls(parent)
    policy_files=['term_explainer/online/visual_review.py','term_explainer/skills/explain-research-term/references/visual-review.md']
    manifest=dict(kind='lesson',diagnostic='visual-intent-v1',calibration='review-v2',model_allowed=True,network_allowed=False,parent=DRIFT,input_hash=hashlib.sha256(json.dumps(cases,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),policy_hashes={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in policy_files})
    identity=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()[:20]
    # A completed identical run remains readable after the phase allowance is spent.
    with store.connection() as db:
        existing=db.execute('SELECT body FROM jobs WHERE owner_id=? AND idem=?',(owner['id'] if owner else '', 'review-calibration-'+identity)).fetchone()
    existing=json.loads(existing['body']) if existing else None
    caps=phase_caps(rows,existing['id'] if existing else '')
    report=dict(mode='execute' if args.execute else 'dry-run-no-requests',key_present=bool(os.environ.get('DEEPSEEK_API_KEY')),budget_before=before,remaining_phase=caps,max_new_requests=min(3,caps['max_job_calls']),network_requests=0,pdf_rereads=0,input_hash=identity)
    print(json.dumps(report,ensure_ascii=False),flush=True)
    if not args.execute:return
    if owner is None:raise ValueError('Existing active test invite required')
    job=existing or store.create_job(owner['id'],'review-calibration-'+identity,manifest,max_pending=10)
    if job['state']=='draft':job=store.enqueue(job['owner_id'],job['id'],job['version'],dict(checkpoint=dict(budget_start=before)),max_queue=10)
    def runner(claim):
        with store.connection() as db:
            fresh=[dict(job_id=r['job_id'],operation=r['operation'],reserved_tokens=r['reserved_tokens'],diagnostic=json.loads(r['body'])['manifest'].get('diagnostic')) for r in db.execute('SELECT p.job_id,p.operation,p.reserved_tokens,j.body FROM provider_calls p JOIN jobs j ON p.job_id=j.id')]
        cap=phase_caps(fresh,claim['id']);cap['max_job_calls']=min(3,cap['max_job_calls'])
        bounded=replace(config,limits=replace(config.limits,**cap,max_daily_calls=110,max_daily_tokens=CAPS['tokens'],max_output_tokens=4096,max_job_network_calls=1))
        provider=BudgetedProvider(bounded,store,files,claim,live.LiveExternal(store,DeepSeekClient(model='deepseek-flash',max_calls=3,max_tokens=4096,timeout=300),caps=CAPS))
        cp=deepcopy(claim['checkpoint'])
        for name,r,l,sources in cases:
            if name in cp:continue
            cp[name]=control_review(r,l,sources,provider)
            worker.publish(claim,'running',dict(stage='reviewing',checkpoint=cp))
            print(json.dumps(dict(step=name,outcome=cp[name],calls=provider.calls),ensure_ascii=False),flush=True)
        return worker.publish(claim,'complete',dict(stage='ready',checkpoint=cp))
    worker=Worker(config,store,runner=runner)
    if job['state']=='queued':
        claim=worker.claim(job_id=job['id'])
        if claim is None:raise ValueError('Shared worker busy; no requests sent')
        job=worker.execute(claim)
    expected={'concrete-feedback':'pass','whole-grouped':'revise','category-grouped':'pass'}
    outcomes={name:job['checkpoint'].get(name) for name in expected}
    report.update(job=job['id'],state=job['state'],progress=job['progress'],budget_start=job['checkpoint'].get('budget_start'),budget_after=live.check_live_budget(store,caps=CAPS),outcomes=outcomes,expected=expected,matched={name:bool(value and value.get('protocol_status')=='valid' and value.get('decision')==expected[name]) for name,value in outcomes.items()},limitations='One attempt per control; questions now match terms. Not a same-input causal comparison or reliability estimate.')
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'live-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False),flush=True)
    if job['state']!='complete':raise SystemExit(2)

if __name__=='__main__':main()
