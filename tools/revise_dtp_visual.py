"""Offline, reversible DTP worked-example revision; no provider or network."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from term_explainer.contract import validate_request,validate_result
from term_explainer.figures import render_visual
from term_explainer.full_job import fingerprint
from term_explainer.reader import build_preview
from term_explainer.worked_visual import prepare_pairwise
from tools.read_term_sections import atomic_write,load_json
from tools.run_term_explainer import summary


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true');args=parser.parse_args(argv)
    root=Path(__file__).resolve().parents[1]
    folder=root/'.superpowers/sdd/2026-10-18-personal-term-explainer-phase1/live/dtp-user-pdf/dtp-complete-run'
    lock=None;lock_path=folder/'job.lock'
    try:
        if args.apply:lock=lock_path.open('x',encoding='utf-8')
        state=load_json(folder/'job.json',16777216);payload=load_json(folder/'input.json')
        if state['stage']!='complete' or state['input_hash']!=fingerprint(payload):raise ValueError('Expected the completed unchanged task')
        if hashlib.sha256(payload['source']['text'].encode()).hexdigest()!=state['reading']['source_hash']:raise ValueError('Original paper changed')
        baseline_path=folder/'reconciliation/before-pairwise-visual-job.json'
        baseline=load_json(baseline_path,16777216) if baseline_path.exists() else state
        if baseline['input_hash']!=state['input_hash']:raise ValueError('Original visual backup belongs to another input')
        new=deepcopy(state);lesson=new['lesson'];original=deepcopy(baseline['lesson']['visual'])
        lesson['visual']=dict(kind='story',title='同一份作答，怎样得到责任感的匹配记录？',origin='teaching',refs=original['refs'],
            learning_goal='理解逐对核对：在同一陈述对内比较参照选择和实际选择。',
            adds_beyond_prose='提供一位受测者的完整三条排序，具体显示两次核对及由此得到的0/1记录。',
            takeaway='按A与B、A与C的顺序核对，得到匹配记录[0, 1]；这些记录进入责任感的模型估计。图中排序为教学示例。',
            alt='教学示例：A按计划完成任务代表责任感，B主动交谈代表沟通，C尝试陌生活动代表开放性，三条均为正向描述。小林排序B、A、C。责任感参照在A与B、A与C两对都选A；小林分别选B与A，因此记录为0、1。',
            payload=dict(layout='pairwise_match',items=[dict(id='A',label='按计划完成任务',detail='责任感'),
                dict(id='B',label='主动与人交谈',detail='沟通'),dict(id='C',label='尝试陌生活动',detail='开放性')],
                example_label='小林的排序（更像自己在前）',order=['B','A','C'],reference_label='责任感占优时的参照',observed_label='小林实选',
                rows=[dict(pair=['A','B'],reference='A'),dict(pair=['A','C'],reference='A')],
                scope_note='三条均假设正向计分。责任感只核对含A的两对；B与C留给其他特质。',
                output_label='匹配记录',next_label='模型估计责任感水平'))
        block=next(b for b in lesson['blocks'] if b['id']=='plain_explanation')
        for paragraph in block['paragraphs']:
            paragraph['text']=paragraph['text'].replace('图中只演示一对陈述，帮助理解“选择—参照—匹配”的关系。','图中用同一人的排序，展示责任感相关两对陈述怎样得到匹配记录。')
        lesson['provenance']['visual_logic_review']=dict(basis='provided_paper_matching_rule_and_explicit_teaching_example',new_api_calls=0,
            original_visual_hash=fingerprint(original),source_rule='equal observed and reference choice yields 1, otherwise 0',
            example_data='constructed teaching ranking, not empirical paper data',human_scientific_signoff='pending')
        request=validate_request(dict(payload['request'],sources=state.get('reader_sources',[state['selected_source']])))
        result=validate_result(lesson,request);new['lesson']=asdict(result)
        derived=prepare_pairwise(result.visual['payload'])
        if args.apply:
            audit=folder/'reconciliation';audit.mkdir(exist_ok=True)
            backup=audit/'before-pairwise-visual-job.json'
            if not backup.exists():atomic_write(backup,state)
            old_figures=audit/'before-pairwise-visual-figures'
            if not old_figures.exists():shutil.copytree(folder/'preview/figures',old_figures)
            old_page=audit/'before-pairwise-visual-index.html'
            if not old_page.exists():shutil.copy2(folder/'preview/index.html',old_page)
            # Render and pass PDF QA before changing the live local preview/job.
            candidate=audit/'pairwise-visual-candidate'
            figures=render_visual(result.visual,candidate,run_external_qa=True)
            shutil.copytree(candidate,folder/'preview/figures',dirs_exist_ok=True)
            build_preview(result,figures,folder/'preview',sources=request.sources,catalog=request.catalog+request.known_terms)
            atomic_write(folder/'lesson.json',new['lesson']);atomic_write(folder/'job.json',new);atomic_write(folder/'report.json',summary(new))
        print(json.dumps(dict(applied=args.apply,api_calls=0,observed=derived['observed'],reference=derived['references'],matches=derived['matches'],
            reading_and_evidence_unchanged=state['reading']==new['reading'] and state['evidence']==new['evidence']),ensure_ascii=False,indent=2))
        return 0
    except (ValueError,KeyError,TypeError,OSError,StopIteration) as error:
        print(json.dumps(dict(error='visual_revision_stopped',message=str(error),api_calls=0),ensure_ascii=False),file=sys.stderr);return 2
    finally:
        if lock is not None:lock.close();lock_path.unlink()


if __name__=='__main__':raise SystemExit(main())
