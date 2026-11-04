"""Offline reviewed multi-source edition; preserves original and failed model drafts."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
import hashlib,json,re,shutil,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from term_explainer.contract import validate_request,validate_result,used_source_ids
from term_explainer.full_job import fingerprint
from term_explainer.reader import build_preview
from term_explainer.literature import deduplicate_sources
from tools.read_term_sections import load_json,atomic_write
from tools.run_term_explainer import summary


def main():
    base=Path(__file__).resolve().parents[1]/'.superpowers/sdd/2026-10-18-personal-term-explainer-phase1/live/dtp-user-pdf'
    original=base/'dtp-complete-run';folder=base/'dtp-multi-literature-run'
    lock=(folder/'job.lock').open('x',encoding='utf-8')
    try:
        state=load_json(folder/'job.json',16777216);payload=load_json(folder/'input.json')
        old=load_json(original/'lesson.json');origin=state['enrichment_origin']
        if state['stage']!='lesson' or state['input_hash']!=fingerprint(payload) or origin['original_lesson_hash']!=fingerprint(old):raise ValueError('Original or enrichment state changed')
        if state.get('reviewed_multi_delivery'):raise ValueError('Already finalized')
        sources=state['reader_sources'];lookup={s['id']:s for s in sources}
        lesson=deepcopy(old)
        detail=next(b for b in lesson['blocks'] if b['id']=='detailed_explanation')['paragraphs'][0]
        usage=next(b for b in lesson['blocks'] if b['id']=='how_to_use')['paragraphs'][0]
        def locate(sid,pattern):
            text=lookup[sid]['text'];m=re.search(pattern,text,re.I)
            if not m:raise ValueError('Expected reviewed source passage is absent')
            return dict(source_id=sid,start=max(0,m.start()-100),end=min(len(text),m.end()+1000))
        brown=locate('brown2011',r'each item elicits a utility')
        nie=locate('nie2024',r'three major components')
        detail.update(text='TIRT从每条陈述对人的“吸引力”出发，用两条陈述的差异解释偏好；DTP先建立特质占优时的参照，再估计实际偏好与参照的一致模式。同一份排序可以有不同的计分模型，关键在于模型把什么当作要解释的结果。',
            emphasis=['同一份排序可以有不同的计分模型'],refs=[*detail['refs'],brown])
        usage.update(text='选用方法时分清三件事：问卷怎样要求作答、陈述怎样反映特质、模型怎样解释条目间的选择。它们共同决定计分模型。DTP适用于多维迫选资料，须把组内偏好转换为项目对记录。',
            emphasis=['问卷怎样要求作答、陈述怎样反映特质、模型怎样解释条目间的选择'],refs=[*usage['refs'],nie])
        readable={s['id'] for s in sources}
        lesson['source_relations']=[deepcopy(r) for r in state['evidence']['source_relations'] if {r['source'],r['target']}<=readable]
        count=sum(len(p['text']) for b in lesson['blocks'] for p in b['paragraphs'])
        if count>origin['body_char_limit']:raise ValueError('Reviewed edit exceeds original body size')
        source_map={sid:s['work_id'] for s in deduplicate_sources(sources) for sid in [s['id'],*s['aliases']]}
        works={source_map[sid] for sid in used_source_ids(lesson)}
        if len(works)!=3:raise ValueError('Expected three actually used independent works')
        lesson['provenance']['multi_literature_review']=dict(
            basis='previous_accepted_lesson_plus_inspected_related_method_sections',automatic_generation_passed=False,
            original_body_chars=origin['body_char_limit'],reviewed_body_chars=count,used_independent_works=3,
            sources_read_scope='Primary paper retained; selected method sections of two references read, not their entire papers.',
            new_paid_generation_attempts_preserved=True,human_scientific_signoff='pending',
            supporting_positions=[brown,nie],source_hashes={s['id']:hashlib.sha256(s['text'].encode()).hexdigest() for s in sources})
        request=validate_request(dict(payload['request'],sources=sources));result=validate_result(lesson,request)
        for key in ('visual','formulas','quiz','relations','glossary'):
            if asdict(result)[key]!=old[key]:raise ValueError('Approved nonprose module changed')
        atomic_write(folder/'before-reviewed-multi-delivery-job.json',state)
        shutil.copytree(original/'preview/figures',folder/'preview/figures',dirs_exist_ok=True)
        assets=SimpleNamespace(desktop='figure.svg',mobile='figure-mobile.svg',alt=result.visual['alt'])
        page=build_preview(result,assets,folder/'preview',sources=sources,catalog=request.catalog+request.known_terms)
        state.update(stage='complete',lesson=asdict(result),output_page=str(page.resolve()),reviewed_multi_delivery=True,requires_human_review=True)
        atomic_write(folder/'lesson.json',state['lesson']);atomic_write(folder/'job.json',state);atomic_write(folder/'report.json',summary(state))
        print(json.dumps(dict(body_before=origin['body_char_limit'],body_after=count,used_works=3,new_calls_for_local_edit=0,report=summary(state)),ensure_ascii=False,indent=2))
    finally:lock.close();(folder/'job.lock').unlink()


if __name__=='__main__':main()
