"""Private, source-grounded correction of the already-generated SJT example; zero model calls."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from term_explainer.figures import render_visual
from term_explainer.library_export import export_package,public_catalogue
from term_explainer.reader import build_preview
from term_explainer.term_identity import verified_identity


def revise_lesson(original,sources):
    if original['term']['zh']!='情境判断测验':raise ValueError('This curated correction is only for the reviewed SJT example')
    lesson=deepcopy(original);proposal=None
    for source in sources:
        match=re.search(r'\bsituational judge?ment tests?\b',source['text'],re.I)
        if match:
            proposal={'en':match[0],'refs':[dict(source_id=source['id'],start=match.start(),end=match.end())]};break
    if proposal is None:raise ValueError('No literal English term in the provided source')
    identity=verified_identity(lesson['term'],proposal,sources)
    lesson.setdefault('provenance',{}).update(verified_identity=identity,original_anchor=deepcopy(original['term']),
        human_scientific_review='pending',visual_logic_review='curated_revision_pending_human',
        revision_basis='existing_source_and_teaching_example_no_new_model_calls')
    refs=deepcopy(next(b for b in lesson['blocks'] if b['id']=='operational_definition')['paragraphs'][0]['refs'])
    lesson['visual']=dict(kind='story',origin='teaching',title='同一情境，比较行动，再按参照解释选择',
        alt='虚构教学例子：组员当众质疑方案。A立刻争辩、B先问具体顾虑、C回避不回应。受测者选B；本例预设A零分、B两分、C一分，得到两分。',
        takeaway='沿高亮的B核对作答与参照：看的是在给定情境下如何判断行动。这里的情境、0/2/1分和参照均为教学约定，不是论文原题、实测结果或通用标准答案。',
        learning_goal='看懂情境材料、行动选项、受测者选择和评分参照如何构成一个情境判断题。',
        adds_beyond_prose='用同一具体题目把行动B与参照B两分对齐；保留A和C作为可观察的替代行动，区别方法本身与某次测验的难度统计。',
        refs=refs,presentation=dict(version=1,focus='process',numeric_role='exact',layout='story',interaction='none'),
        payload=dict(layout='scenes',ordered=True,scenes=[
            dict(title='01 共同面对的情境',objects=[dict(id='team',kind='group',label='组员质疑方案',state='neutral'),dict(id='you',kind='person',label='你会怎样回应？',state='neutral')],connections=[dict(from_='team',to='you',label='情境呈现',relation='sequence')]),
            dict(title='02 受测者从行动中选B',objects=[dict(id='a',kind='item',label='A：立刻争辩',state='neutral'),dict(id='b',kind='item',label='B：先问具体顾虑',state='selected'),dict(id='c',kind='item',label='C：回避不回应',state='neutral')],connections=[]),
            dict(title='03 按本例预设参照计分',objects=[dict(id='ka',kind='record',label='A → 0分',state='neutral'),dict(id='kb',kind='record',label='选B → 2分',state='match'),dict(id='kc',kind='record',label='C → 1分',state='neutral')],connections=[]),
        ]))
    for scene in lesson['visual']['payload']['scenes']:
        for edge in scene['connections']:
            if 'from_' in edge:edge['from']=edge.pop('from_')
    return lesson


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();output=args.output.resolve()
    private=(ROOT/'.superpowers/sdd/2026-10-26-generation-hardening').resolve()
    if not output.is_relative_to(private) or output.exists():raise ValueError('Choose a new private correction directory')
    with ZipFile(args.input) as archive:
        package=json.loads(archive.read('library.json'));original=package['revisions'][0]['lesson']
        sources=[e['data'] for e in package['evidence']];lesson=revise_lesson(original,sources)
        output.mkdir(parents=True);originals={}
        for source in package['sources']:
            if source.get('blobHash') and source.get('originalStatus')=='saved':
                name='originals/'+source['blobHash']+'.pdf'
                data=archive.read(name)
                if hashlib.sha256(data).hexdigest()!=source['blobHash']:raise ValueError('Original hash mismatch')
                path=output/(source['blobHash']+'.pdf');path.write_bytes(data);originals[source['localId']]=path
    figures=render_visual(lesson['visual'],output/'figures')
    catalogue=[dict(t,kind='classic') for t in public_catalogue(ROOT/'site/online-release-permissive-v2')['terms']]
    context=[s for s in sources if s['id'] not in originals];archived=[s for s in sources if s['id'] in originals]
    request=dict(request_id='sjt-revision-20261026',term=deepcopy(lesson['term']),sources=context,catalog=catalogue,known_terms=[],network_allowed=False)
    report=export_package(request,lesson,sources=context,archive_sources=archived,originals=originals,
        figures=dict(desktop=figures.desktop,mobile=figures.mobile),term_id=lesson['term']['id'],output=output/'lesson.zip')
    image_dir=output/'preview/figures';image_dir.mkdir(parents=True)
    import shutil
    for name in (figures.desktop,figures.mobile):shutil.copyfile(name,image_dir/Path(name).name)
    preview=build_preview(lesson,figures,output/'preview',sources=context,catalog=catalogue)
    report.update(model_calls=0,original_preserved=True,preview=str(preview),human_review='pending',sha256=hashlib.sha256((output/'lesson.zip').read_bytes()).hexdigest())
    (output/'revision-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
