"""Locally reviewed DTP teaching example; reuse paid draft, no provider or key.

The original draft and job are preserved. This one-off editorial step is explicit
and fingerprint-bound; it is not an automatic scientific approval mechanism.
"""
from copy import deepcopy
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from term_explainer.contract import validate_request,validate_result
from term_explainer.full_job import fingerprint,deliver
from tools.read_term_sections import load_json,atomic_write
from tools.run_term_explainer import summary


def curate(state,payload):
    if (state['stage']!='needs_sources' or state.get('last_error',{}).get('code')!='lesson_partial'
            or fingerprint(state['lesson'])!='15492e44c3f9f4e16ff8da1694fbd55261b8213c8c8634217064bc62c0acb77f'
            or fingerprint(payload)!=state['input_hash']):
        raise ValueError('This review applies only to the inspected original DTP draft')
    if not state['evidence'].get('can_generate') or state['evidence'].get('missing_modules'):
        raise ValueError('Core teaching evidence has not passed the source-first gate')
    lesson=deepcopy(state['lesson']); original_missing=deepcopy(lesson['missing_evidence'])
    sid=state['selected_source']['id']
    def refs(*numbers): return [dict(source_id=sid,span_id=f'{sid}#c{n:04d}') for n in numbers]
    def para(text,*numbers,emphasis=(),kind='factual'):
        return dict(text=text,emphasis=list(emphasis),kind=kind,refs=refs(*numbers))
    blocks={b['id']:b for b in lesson['blocks']}
    blocks['real_question']['paragraphs']=[para('问卷要求大家在几条性格陈述中排出“最像我”和“最不像我”。收回这些选择后，怎样得到责任感、沟通等多个特质各自的分数？',0,emphasis=['多个特质各自的分数']),para('DTP提供一种计分思路：先为每个特质建立一个参照选择模式，再看实际选择与这个模式怎样匹配。',0,2,emphasis=['参照选择模式'])]
    blocks['plain_explanation']['heading']='通俗解释：给每个特质准备一张参照卡'
    blocks['plain_explanation']['paragraphs']=[para('想象你在看三条日常描述：“我会按计划完成任务”“我会主动与人交谈”“我愿意尝试陌生的活动”。它们分别用来演示责任感、沟通和开放性；这里假设三条都是正向描述。',4,kind='analogy'),para('如果要了解责任感，就先做一张“责任感明显占优时会怎样选”的参照卡：在责任感与沟通、责任感与开放性的比较中，都预期优先选责任感描述。沟通与开放性之间的那一对留给其他特质使用。',2,4,emphasis=['参照卡'],kind='analogy'),para('接着把一个人的实际选择拿来对照：与参照一致记1，不一致记0。DTP把这些匹配记录交给模型，估计这个人的特质水平。图中只演示一对陈述，帮助理解“选择—参照—匹配”的关系。',5,emphasis=['一致记1，不一致记0'],kind='analogy')]
    detail=blocks['detailed_explanation']['paragraphs']
    detail[0]=para('DTP关注观察到的项目对偏好与DRV参照模式的匹配概率。论文将它与TIRT作比较：TIRT直接对项目对中一个项目优于另一个项目的偏好概率建模。理解这一差别，有助于认清两种方法各自在估计什么。',23,emphasis=['匹配概率'])
    detail[1]=para('在DTP的模型中，下标i标记一个项目对。匹配概率由个人特质水平和该项目对的参数共同决定。IRT路线使用区分度αᵢ与位置参数βᵢ；DSM路线使用自己的D-scale参数。',8,12,emphasis=['项目对'])
    detail[3]=para('D-scale的范围为0到1，论文把特质占优的参照标准固定在D=1。D分数越靠近1，越接近这一参照标准。两条量尺的标准误随位置变化的方式不同，阅读精度信息时应同时看清所用量尺。',7,13,emphasis=['D=1'])
    detail[4]=para('DTP分别估计各个特质，估计模型中未显式纳入特质间相关。作者认为跨特质的项目对匹配可能包含部分特质间信息，并指出实际效率与理论严谨性的平衡仍需进一步研究。',28,29,emphasis=['分别估计各个特质'])
    usage=blocks['how_to_use']['paragraphs']
    usage[2]=para('方法顺序是：把每组选择转成项目对二值偏好；依据特质归属与键控方向构造DRV；逐特质生成匹配记录；选择RFM2或2PL，估计项目对参数与个人特质水平。得到分数仍需要模型估计这一步。',14,15,emphasis=['模型估计'])
    usage[3]=para('解释得分时，先确定使用的量尺。D-scale分数可结合D=1参照标准理解；IRT路线的分数位于logit量尺。两种路线都从项目对的匹配模式出发估计特质，不能用某一选项被选择的次数直接代替最终特质分数。',7,12,emphasis=['使用的量尺'])
    lesson['blocks'].append(dict(id='academic_expression',heading='学术表达：方法段落示例',paragraphs=[para('以下以IRT路线示范方法写法，不包含虚构的分析结果：',15,kind='illustration'),para('本研究采用优势特质剖面计分法（DTP）对多维迫选问卷进行计分。根据条目的特质归属及键控方向，分别构造各特质的优势反应向量；将观察到的项目对偏好与相应参照比较，生成二值匹配记录，并采用双参数逻辑模型分别估计各特质水平。',14,15,kind='illustration')]))
    lesson['formulas']=[dict(latex=r'P_i(\theta)=\frac{1}{1+\exp[-\alpha_i(\theta-\beta_i)]}',
        symbols=[dict(symbol='i',meaning='一个包含目标特质条目的项目对'),dict(symbol=r'P_i(\theta)',meaning='特质水平为θ时，该项目对的实际偏好与DRV参照一致的概率'),dict(symbol=r'\theta',meaning='个人特质水平，位于IRT的logit量尺'),dict(symbol=r'\alpha_i',meaning='该项目对的匹配区分度'),dict(symbol=r'\beta_i',meaning='该项目对匹配概率为0.5时的特质位置')],refs=refs(11,12))]
    lesson['visual']=dict(kind='story',title='把一对选择变成匹配记录',origin='teaching',
        takeaway='这里假设两条陈述都正向计分，演示责任感相关的一对。完整计分会对各特质重复匹配，再交给模型估计。',
        alt='三幕教学故事：先比较责任感和沟通陈述；责任感占优的参照预期选择责任感；实际选择责任感得到匹配1，选择沟通得到匹配0。',refs=refs(2,4,5),
        payload=dict(scenes=[
            dict(title='把日常描述放成一对',objects=[dict(id='a',kind='item',label='按计划完成任务',state='neutral'),dict(id='b',kind='item',label='主动与人交谈',state='neutral')],connections=[dict(from_='a',to='b',label='比较选择')]),
            dict(title='责任感占优的参照',objects=[dict(id='ref',kind='record',label='参照：优先责任',state='selected'),dict(id='obs',kind='record',label='实际：优先责任',state='match')],connections=[dict(from_='ref',to='obs',label='逐对核对')]),
            dict(title='按一致程度留下记录',objects=[dict(id='yes',kind='record',label='选责任：匹配1',state='match'),dict(id='no',kind='record',label='选沟通：匹配0',state='mismatch')],connections=[])]))
    for scene in lesson['visual']['payload']['scenes']:
        for edge in scene['connections']: edge['from']=edge.pop('from_')
    lesson['relations']=[dict(target='standard-error',type='prerequisites',reason='理解估计精度时，需要把标准误与相应量尺一起阅读。',refs=refs(7,13)),dict(target='correlation-coefficient',type='prerequisites',reason='论文用方法间得分的相关来比较一致程度；阅读这些比较先了解相关系数。',refs=refs(22,23))]
    lesson.update(status='complete',missing_evidence=[],limitations=[
        dict(text='论文展示了特定模拟设计和真实测评数据下的表现。面向新的样本规模、题组结构或测评用途，仍需检验估计稳定性与适用条件。',refs=refs(15,22,29)),
        dict(text='本文的主要比较证据来自DTP与其他计分方法所得分数的关系。面向新的使用目的，外部效标关系与决策用途仍需相应研究支持。',refs=refs(17,23,29))])
    lesson['provenance'].update(local_editorial_review=dict(original_lesson_hash=fingerprint(state['lesson']),
        original_status=state['lesson']['status'],original_missing_evidence=original_missing,
        decision='research_limits_preserved_separately_after_source_review',new_api_calls=0,
        formula_visual_checked=True,formula_note='Compared to original displayed Equation (3); alpha/beta notation preserved.',
        edits=['separate research limits from core evidence gaps','clarify everyday example and positive keying','preserve 2PL parameter notation','source-grounded knowledge links','method-writing illustration','simplify story geometry'],
        human_scientific_signoff='pending'))
    request=validate_request(dict(payload['request'],sources=[state['selected_source']]))
    return validate_result(lesson,request)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--refresh',action='store_true',help='Locally re-export an already reviewed lesson; no model calls.')
    args=parser.parse_args(argv)
    root=Path(__file__).resolve().parents[1]
    folder=root/'.superpowers/sdd/2026-10-18-personal-term-explainer-phase1/live/dtp-user-pdf/dtp-complete-run'
    lock=None; lock_path=folder/'job.lock'; state=None
    try:
        if args.apply: lock=lock_path.open('x',encoding='utf-8')
        state=load_json(folder/'job.json',16777216); payload=load_json(folder/'input.json')
        if state['stage']=='complete':
            if args.apply and args.refresh: state['stage']='render'
            else:
                print(json.dumps(summary(state),ensure_ascii=False,indent=2)); return 0
        if state['stage']!='render':
            lesson=curate(state,payload)
            if not args.apply:
                print(json.dumps(dict(validated=True,api_calls=0,blocks=len(lesson.blocks),relations=len(lesson.relations),limitations=len(lesson.limitations)),ensure_ascii=False,indent=2)); return 0
            audit=folder/'reconciliation'; audit.mkdir(exist_ok=True)
            for name,value in [('lesson-original-job.json',state),('lesson-original.json',state['lesson'])]:
                target=audit/name
                if target.exists() and fingerprint(load_json(target,16777216))!=fingerprint(value):
                    raise ValueError('Existing original differs; not overwritten')
                if not target.exists(): atomic_write(target,value)
            from dataclasses import asdict
            state.update(stage='render',lesson=asdict(lesson)); state.pop('last_error',None)
        if not args.apply: print('Rendering is ready, no action taken.'); return 0
        def save(value):
            atomic_write(folder/'job.json',value); atomic_write(folder/'report.json',summary(value))
        atomic_write(folder/'lesson.json',state['lesson']); save(state)
        deliver(state,payload,None,save,folder,external_qa=True)
        print(json.dumps(summary(state),ensure_ascii=False,indent=2)); return 0
    except (ValueError,KeyError,TypeError,OSError) as error:
        print(json.dumps(dict(error='local_review_or_export_failed',message=str(error),api_calls=0),ensure_ascii=False),file=sys.stderr)
        return 2
    finally:
        if lock is not None:
            lock.close(); lock_path.unlink()


if __name__=='__main__': raise SystemExit(main())
