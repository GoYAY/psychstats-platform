"""Bounded diagnostic samples and one real visual-only delivery; no deployment."""
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path
import argparse, hashlib, json, os, sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import tools.qa_online_generation_live as live
from term_explainer.online.store import OnlineStore
from term_explainer.online.files import PrivateFiles
from term_explainer.online.worker import Worker
from term_explainer.online.provider import BudgetedProvider
from term_explainer.online.delivery import build_delivery
from term_explainer.deepseek import DeepSeekClient
from term_explainer.pipeline import _parse
from term_explainer.contract import validate_request, validate_result
from term_explainer.figures import validate_visual

CAPS=dict(model=110,network=10,tokens=1814277)
PARENT='job-86e16cc4c9070fb5066d032ef8af5af5'
OUT=ROOT/'logs/visual-teaching-model-2026-10-24'
SKILL=ROOT/'term_explainer/skills/explain-research-term'

def policy(guided):
    main=(SKILL/'SKILL.md').read_text(encoding='utf-8')
    reference=(SKILL/'references/instant-visuals.md').read_text(encoding='utf-8')
    if not guided:
        main='\n'.join(line for line in main.splitlines() if not line.startswith('先确定读者需要观察整体'))
        start=reference.index('## 按学习任务分配视觉权重')
        end=reference.index('## 只提交数据，不提交组件')
        reference=reference[:start]+reference[end:]
        start=reference.index('宿主明确声明已接入相应图型')
        end=reference.index('\n\nBklit',start)
        reference=reference[:start]+'只有宿主明确声明已接入相应图型，网页才提供即时交互：悬停读精确值；点击、触屏或键盘选择已有对象并保留对应解释；再次选择或Esc撤销。关键结论、轴名与单位在不操作时也可读。解释依据已有数据及来源，不在悬停/点击时调用模型或联网。颜色之外保留标签、数值或形状编码。'+reference[end:]
        reference=reference.replace('先检查不操作时能否看出学习目标中的主要关系、整体与局部是否选对、读数和控件的权重是否合理。','').replace('也不证明模型已能稳定遵循教学取舍。','')
    return '\n\n'.join((main,(SKILL/'references/lesson-contract.md').read_text(encoding='utf-8'),reference))

def contexts(parent):
    data=json.loads((ROOT/'site/content/plain_visuals/foundations.json').read_text(encoding='utf-8'))['central-tendency-and-dispersion']['chart']['series']
    whole=dict(anchor={'zh':'集中趋势与离散程度','definition':'集中趋势描述数据的中心位置，离散程度描述观测值的分散程度。'},question='两个班整体的成绩状况有什么区别？请为通俗解释配一个图，帮助初学者观察。',teaching_data=data,data_origin='明确的教学合成数据；每一对数值是分值和人数。',host_capabilities=dict(interactive_chart_types=['bar'],static_visuals=True,model_code_allowed=False))
    exact=dict(anchor={'zh':'频数分布','definition':'按类别记录各类别出现的次数。'},question='希望从图里确认选择“满意”的准确人数，并对照其他选项。',teaching_data={'categories':['非常不满意','不满意','满意','非常满意'],'counts':[12,23,68,17]},data_origin='教学合成数据，120份问卷，每人只选一项。',host_capabilities=whole['host_capabilities'])
    cp=parent['checkpoint'];lesson=cp['lesson'];old=lesson['visual'];sources=cp['decision']['sources']
    indexed={s['id']:s for s in sources}
    snippets=[dict(ref=r,text=indexed[r['source_id']]['text'][r['start']:r['end']]) for r in old['refs']]
    drift=dict(anchor=cp['decision']['request']['term'],question='请为认知漂移的通俗解释配一个互补的具体示例图。仅修订图示，原样保留输入refs。',evidence=snippets,refs=old['refs'],teaching_context=[b for b in lesson['blocks'] if b['id'] in ('plain_explanation','detailed_explanation')],host_capabilities=whole['host_capabilities'])
    return whole,exact,drift

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    dbpath=live.RUN/'private/jobs.sqlite'
    if not dbpath.is_file():raise ValueError('Existing shared ledger required')
    config=live.configuration();config=replace(config,limits=replace(config.limits,max_job_calls=12,max_daily_calls=110,max_job_tokens=320000,max_daily_tokens=CAPS['tokens'],max_output_tokens=16384))
    store=OnlineStore(dbpath);files=PrivateFiles(config.private_root/'tasks')
    before=live.check_live_budget(store,caps=CAPS)
    with store.connection() as db:
        parent=json.loads(db.execute('SELECT body FROM jobs WHERE id=?',(PARENT,)).fetchone()['body'])
        owner=db.execute('SELECT id FROM invites WHERE revoked=0 AND expires>? ORDER BY created DESC LIMIT 1',(store.clock(),)).fetchone()
    whole,exact,drift=contexts(parent)
    prompts={k:policy(k=='guided') for k in ('control','guided')}
    suffix='\n本次只做图示编排诊断，不生成完整科普。只输出JSON {"visual":现有visual合同对象,"display_plan":{"focus":"whole/local/process","numeric_role":"exact/relative","layout":"简短布局说明","interaction":{"enabled":true或false,"target":"交互对象或空字符串","reason":"简短理由"}}}。display_plan仅是本次诊断记录，不属于科普包，不发明visual扩展字段。已有教学数据须保留，引用只用输入refs；无refs的合成教学图填[]。每次请求是独立样本。'
    manifest=dict(kind='lesson',model_allowed=True,network_allowed=False,diagnostic='visual-teaching-v1',parent=PARENT,policy_hashes={k:hashlib.sha256(v.encode()).hexdigest() for k,v in prompts.items()},contexts=[whole,exact,drift])
    identity=hashlib.sha256(json.dumps(manifest,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:20]
    print(json.dumps(dict(mode='execute' if args.execute else 'dry-run',key_present=bool(os.environ.get('DEEPSEEK_API_KEY')),active_test_invite=owner is not None,budget_before=before,max_new_requests=12,max_job_tokens=320000,network_requests=0,source_rereads=0,input_evidence_chars=sum(len(x['text']) for x in drift['evidence']),policy_hashes=manifest['policy_hashes']),ensure_ascii=False),flush=True)
    if not args.execute:return
    if owner is None:raise ValueError('No active existing local test invitation')
    job=store.create_job(owner['id'],'visual-teaching-v1-'+identity,manifest,max_pending=10)
    if job['state']=='draft':job=store.enqueue(job['owner_id'],job['id'],job['version'],dict(checkpoint={'samples':[]}),max_queue=10)
    def runner(claim):
        client=DeepSeekClient(model='deepseek-flash',max_calls=12,max_tokens=16384,timeout=300)
        provider=BudgetedProvider(config,store,files,claim,live.LiveExternal(store,client,caps=CAPS))
        cp=deepcopy(claim['checkpoint'])
        cases=[(variant,i,whole) for i in range(5) for variant in ('control','guided')]+[('guided',5,exact),('guided',6,drift)]
        for variant,i,context in cases:
            sample_id=f'{variant}-{i}'
            if any(s['id']==sample_id for s in cp['samples']):continue
            reply=provider.generate([dict(role='system',content=prompts[variant]+suffix),dict(role='user',content=json.dumps(dict(context,sample_id=sample_id),ensure_ascii=False))])
            sample=dict(id=sample_id,variant=variant,case='whole' if i<5 else 'exact' if i==5 else 'drift',usage=reply.usage)
            try:
                value=_parse(reply)
                if set(value)!={'visual','display_plan'}:raise ValueError('Diagnostic response shape mismatch')
                validate_visual(value['visual']);sample.update(value,structural_status='pass')
            except ValueError as error:sample.update(structural_status='fail',error=str(error))
            cp['samples'].append(sample)
            worker.publish(claim,'running',dict(stage='visual-diagnostic',checkpoint=cp))
            print(json.dumps(dict(sample=sample_id,case=sample['case'],structural_status=sample['structural_status'],tokens=reply.usage.get('total_tokens')),ensure_ascii=False),flush=True)
        final=cp['samples'][-1]
        if final['structural_status']!='pass':raise ValueError('Drift visual invalid; kept raw receipt, no repair call')
        lesson=deepcopy(parent['checkpoint']['lesson']);lesson['visual']=final['visual']
        if lesson['visual']['refs']!=parent['checkpoint']['lesson']['visual']['refs']:raise ValueError('Evidence references changed; no source-free delivery')
        decision=parent['checkpoint']['decision'];sources=decision['sources']
        lesson=asdict(validate_result(lesson,validate_request(dict(decision['request'],sources=sources))))
        cp['lesson']=lesson;worker.publish(claim,'running',dict(stage='rendering',checkpoint=cp))
        artifact=build_delivery(claim,decision['request'],lesson,sources,files,qa_dir=config.figure_qa_dir,font_path=config.cjk_font)
        return worker.publish(claim,'complete',dict(stage='ready-for-review',checkpoint=cp,result=artifact,usage=dict(calls=provider.calls)))
    worker=Worker(config,store,runner=runner)
    if job['state']=='queued':
        claim=worker.claim(job_id=job['id'])
        if claim is None:raise ValueError('Shared worker busy; no request sent')
        job=worker.execute(claim)
    report=dict(job=job['id'],state=job['state'],progress=job['progress'],result=job.get('result'),samples=job['checkpoint']['samples'],budget_before=before,budget_after=live.check_live_budget(store,caps=CAPS),source_rereads=0,parent=PARENT)
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'live-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='samples'},ensure_ascii=False),flush=True)
    if job['state']!='complete':raise SystemExit(1)

if __name__=='__main__':main()
