"""Create a private, versioned teaching-visual revision without model calls."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from term_explainer.figures import FigureAssets, render_visual
from term_explainer.reader import build_preview
from tools.read_term_sections import atomic_write


def revise_lesson(original):
    lesson=deepcopy(original)
    lesson['content_id']=original['content_id']+'-operational-v1'
    refs=deepcopy(original.get('visual',{}).get('refs',[]))
    lesson['visual']=dict(kind='story',title='偏好与判断依据怎样在互动中来回传递',
        alt='同一研究者在三轮互动中实际比较的候选为3、2、1项；人的访谈偏好进入AI回应，AI提出的体验深度和实施便利又进入下一轮人的判断。',
        takeaway='沿实心候选数出每轮实际比较范围；再沿暖色曲线追踪一个新依据从AI回应进入后续判断。引入其他方法或依据时，比较范围也可以扩大。',
        learning_goal='追踪双方如何改变下一轮的提问与回应，并能指出可观察的比较范围。',
        adds_beyond_prose='同一组可计数候选与有来源的依据标签贯穿三个回合，直接显示双向作用的内容和顺序。',
        origin='teaching',refs=refs,payload={
            'layout':'feedback_trace','example_label':'教学情境与示例数据',
            'scope_note':'候选计数只描述这条虚构互动轨迹；新的问题和依据也可以拓展比较范围。',
            'choices':[{'id':'a','label':'访谈'},{'id':'b','label':'问卷'},{'id':'c','label':'实验'}],
            'criteria':[{'id':'depth','label':'体验深度'},{'id':'feasible','label':'实施便利'}],
            'turns':[
                {'id':'t1','userCompared':['a','b','c'],'userPreferred':'a','aiFocus':['a','b'],'aiIntroduced':['depth'],'userAdopted':[]},
                {'id':'t2','userCompared':['a','b'],'userPreferred':'a','aiFocus':['a'],'aiIntroduced':['feasible'],'userAdopted':[{'criterion':'depth','fromTurn':'t1'}]},
                {'id':'t3','userCompared':['a'],'userPreferred':'a','aiFocus':['a'],'aiIntroduced':[],'userAdopted':[{'criterion':'feasible','fromTurn':'t2'}]},
            ]})
    lesson['provenance']={**lesson.get('provenance',{}),'visual_logic_review':'operational_trace_pending_human_review','automatic_generation_passed':False}
    return lesson


def build_revision_preview(revision_dir):
    """Make an existing private revision viewable without importing its ZIP."""
    revision=Path(revision_dir).resolve()
    lesson=json.loads((revision/'lesson.json').read_text(encoding='utf-8'))
    report=json.loads((revision/'revision-report.json').read_text(encoding='utf-8'))
    figures=FigureAssets(**report['assets'])
    output=revision/'preview';images=output/'figures';images.mkdir(parents=True,exist_ok=True)
    for name in (figures.desktop,figures.mobile):
        path=Path(name);shutil.copyfile(path,images/path.name)
    evidence=revision/'evidence.json'
    sources=json.loads(evidence.read_text(encoding='utf-8')).get('sources',[]) if evidence.is_file() else []
    return build_preview(lesson,figures,output,sources=sources)


def revise_entanglement_visual(input_dir,output_dir,*,run_external_qa=True):
    source=Path(input_dir).resolve();output=Path(output_dir).resolve()
    if source==output or source in output.parents or output in source.parents or output.is_relative_to(ROOT/'site'):
        raise ValueError('Revision output must be private and isolated from the original job')
    if (output/'lesson.json').exists():raise ValueError('Revision already exists; preserve it and choose a new output')
    original=json.loads((source/'lesson.json').read_text(encoding='utf-8'))
    lesson=revise_lesson(original);output.mkdir(parents=True,exist_ok=True)
    for name in ['render-request.json','request.json','evidence.json']:
        if (source/name).is_file():shutil.copyfile(source/name,output/name)
    assets=render_visual(lesson['visual'],output/'figures',run_external_qa=run_external_qa)
    atomic_write(output/'lesson.json',lesson)
    report=dict(status='visual_revision',model_calls=0,prose_unchanged=lesson['blocks']==original['blocks'],
                quiz_unchanged=lesson.get('quiz')==original.get('quiz'),source_lesson_hash=hashlib.sha256((source/'lesson.json').read_bytes()).hexdigest(),
                human_scientific_review='pending',archetype='schematic-led composite',backend='python',
                core_claim='同一偏好及新判断依据在多轮互动中跨双方传递；比较范围可按对象计数。',
                evidence_boundary='文献支撑互动机制；对象与计数为教学构造，不是测量分数或论文结果。',
                assets=vars(assets))
    atomic_write(output/'revision-report.json',report)
    report['output_page']=str(build_revision_preview(output))
    atomic_write(output/'revision-report.json',report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(revise_entanglement_visual(args.input,args.output),ensure_ascii=False,indent=2))
