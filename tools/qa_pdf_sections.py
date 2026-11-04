"""Offline section-routing replay. Never instantiates a live model client."""
import argparse,hashlib,json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from term_explainer.online.sources import parse_source,prepare_sources
from term_explainer.online.config import load_config
from term_explainer.section_structure import heading_role
from term_explainer.deepseek import ModelReply
from tests.term_explainer.online.helpers import environment


class ReadingComplete(Exception):pass


class OfflineReader:
    """Contract-shaped synthetic notes, not an evaluation of scientific reading."""
    def __init__(self):self.read_calls=0;self.selection_attempts=0
    def generate(self,messages,*args,**kwargs):
        context=json.loads(messages[-1]['content'])
        if 'sections' in context:
            self.selection_attempts+=1
            raise ReadingComplete()
        self.read_calls+=1
        source=context['sources'][0];ref=dict(source_id=source['id'],span_id=source['spans'][0]['id'])
        value=dict(anchor_conflicts=[],target_kind='concept',missing_evidence=[],claims=[],source_relations=[],reference_candidates=[],
            reading_notes=[dict(source_id=source['id'],summary='离线结构回放，仅验证文字覆盖，不评价语义理解。',evidence=[ref],identity_check=dict(status='matches',reason='Synthetic routing fixture, not identity evaluation.'))],
            synthesis=[dict(source_id=source['id'],role='uncertain',contribution='离线回放不产生科学结论。',related_source_ids=[],relationship_reason='仅检查路由。',evidence=[ref])],
            rolling_summary='离线结构回放，仅验证章节覆盖，不代表模型理解或科普通过。',key_conditions=[])
        return ModelReply(json.dumps(value,ensure_ascii=False),'offline-structure-fixture',dict(total_tokens=0),'stop')


def replay(pdf):
    before=hashlib.sha256(pdf.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='pdf-structure-offline-') as directory:
        config=load_config(dict(environment(directory),TERM_MAX_JOB_CALLS='60'))
        doc=parse_source(pdf,dict(id='local-paper',name=pdf.name,title=pdf.name,mime='application/pdf'),config.limits)
        request=dict(request_id='offline-structure',term=dict(id='neijuan',zh='内卷',en='',aliases=[],definition=''),question='理解术语的含义与维度。',sources=[],catalog=[],known_terms=[],literature_prompted=True,network_allowed=False)
        snapshots=[];client=OfflineReader()
        try:prepare_sources(request,[doc],client,lambda s:snapshots.append(s),limits=config.limits)
        except ReadingComplete:pass
        else:raise AssertionError('Did not reach evidence selection after reading')
        reading=snapshots[-1]['readings']['local-paper'];sections=reading['sections']
        assert reading['next_section']==len(sections)
        assert len(reading['readings'])==len(sections)
        assert sections[0]['start']==0 and sections[-1]['end']==len(doc['source']['text'])
        assert all(a['end']==b['start'] for a,b in zip(sections,sections[1:]))
        skipped=[]
        for section,handled in zip(sections,reading['readings']):
            assert section['id']==handled['section_id']
            if handled.get('mode')=='local_catalogue':
                assert heading_role(section['title'])=='bibliography'
                skipped.append(section)
        assert hashlib.sha256(pdf.read_bytes()).hexdigest()==before
        return dict(pdf_sha256=before,pdf_unchanged=True,extraction=doc.get('extraction',{}),characters=len(doc['source']['text']),
            text_sha256=hashlib.sha256(doc['source']['text'].encode()).hexdigest(),headings=doc['headings'],sections=len(sections),handled_sections=reading['next_section'],
            local_catalogue=skipped,offline_reading_calls=client.read_calls,selection_attempts=client.selection_attempts,external_calls=0,
            coverage='all original extracted characters assigned; only bibliography catalogued',scientific_reading='not evaluated; synthetic offline fixture')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--pdf',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise SystemExit('Choose a new immutable report path')
    result=replay(a.pdf);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in {'headings','local_catalogue'}},ensure_ascii=False,indent=2))
