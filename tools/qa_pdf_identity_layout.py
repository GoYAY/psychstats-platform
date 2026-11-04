"""Zero-network PDF identity/order regression; never a model-quality verdict."""
import argparse
import hashlib
from io import BytesIO,StringIO
import json
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from pdfminer.converter import TextConverter
import pdfplumber
from term_explainer.online.sources import parse_source,prepare_sources
from term_explainer.online.config import load_config
from term_explainer.deepseek import ModelReply
from tests.term_explainer.online.helpers import environment
from tools.qa_pdf_sections import OfflineReader,ReadingComplete


class InteriorReader(OfflineReader):
    def __init__(self,omit_reference_at=0):
        super().__init__();self.omit_reference_at=omit_reference_at

    def generate(self,messages,*args,**kwargs):
        context=json.loads(messages[-1]['content'])
        if 'sections' not in context:
            assert context['document_identity']['status']=='matches'
        reply=super().generate(messages)
        value=json.loads(reply.content)
        for note in value['reading_notes']:
            note['identity_check']=dict(status='uncertain',reason='本内页未重印完整题名、作者与DOI。')
        if self.read_calls==self.omit_reference_at:value.pop('reference_candidates')
        return ModelReply(json.dumps(value,ensure_ascii=False),reply.model,reply.usage,reply.finish_reason)


def replay(path,*,omit_reference_at=0):
    raw=path.read_bytes();before=hashlib.sha256(raw).hexdigest()
    with tempfile.TemporaryDirectory(prefix='pdf-identity-offline-') as directory:
        config=load_config(dict(environment(directory),TERM_MAX_JOB_CALLS='60'))
        doc=parse_source(path,dict(id='local-paper',name=path.name,title=path.name,mime='application/pdf'),config.limits)
        assert doc['identity_review'] and doc['identity_review']['status']=='matches'
        text=doc['source']['text'];offset=0;legacy_parts=[];changed=[]
        with pdfplumber.open(BytesIO(raw),laparams={}) as pdf:
            assert len(pdf.pages)==len(doc['extraction']['page_offset_map'])
            for page,mapping in zip(pdf.pages,doc['extraction']['page_offset_map']):
                stream=StringIO();device=TextConverter(pdf.rsrcmgr,stream)
                try:device.receive_layout(page.layout);legacy=stream.getvalue().rstrip('\x0c')
                finally:device.close()
                part=text[offset:offset+len(legacy)];offset+=len(legacy)+1
                assert [m['start'] for m in mapping]==[0]+[m['end'] for m in mapping[:-1]]
                sorted_map=sorted(mapping,key=lambda m:m['legacy_start'])
                assert [m['legacy_start'] for m in sorted_map]==[0]+[m['legacy_end'] for m in sorted_map[:-1]]
                assert mapping[-1]['end']==sorted_map[-1]['legacy_end']==len(legacy)
                for m in mapping:assert part[m['start']:m['end']]==legacy[m['legacy_start']:m['legacy_end']]
                legacy_parts.append(legacy);changed.append(part!=legacy)
        assert offset-1==len(text)
        assert hashlib.sha256('\n'.join(legacy_parts).encode()).hexdigest()==doc['extraction']['legacy_text_sha256']
        request=dict(request_id='offline-identity',term=dict(id='example',zh='内卷',en='',aliases=[],definition=''),question='理解术语的含义。',sources=[],catalog=[],known_terms=[],literature_prompted=True,network_allowed=False)
        snapshots=[];client=InteriorReader(omit_reference_at)
        try:prepare_sources(request,[doc],client,lambda state:snapshots.append(state),limits=config.limits)
        except ReadingComplete:pass
        else:raise AssertionError('Did not reach selection')
        reading=snapshots[-1]['readings']['local-paper']
        assert reading['next_section']==len(reading['sections'])
        assert all(not r.get('anchor_conflicts') for r in reading['readings'])
        assert hashlib.sha256(path.read_bytes()).hexdigest()==before
        return dict(pdf_sha256=before,pdf_unchanged=True,characters=len(text),pages=len(changed),
            changed_pages=[i+1 for i,v in enumerate(changed) if v],layout_version=doc['extraction']['layout_version'],
            text_sha256=doc['extraction']['text_sha256'],legacy_text_sha256=doc['extraction']['legacy_text_sha256'],
            lossless_mapping=True,title=doc['source']['title'],doi=doc['source']['doi'],
            identity_status=doc['identity_review']['status'],identity_evidence=doc['identity_review']['evidence'],
            sections=[dict(title=s['title'],start=s['start'],end=s['end']) for s in reading['sections']],
            handled_sections=reading['next_section'],offline_reading_calls=client.read_calls,
            omitted_reference_at=omit_reference_at,analysis_contracts=reading.get('analysis_contracts',{}),
            selection_attempts=client.selection_attempts,external_calls=0,
            scientific_reading='not evaluated; uncertain interior notes are synthetic contract fixtures')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--omit-reference-at',type=int,default=0,help='Offline fixture: omit this field on the Nth section reading')
    args=parser.parse_args()
    if args.out.exists():raise SystemExit('Choose a new immutable report path')
    result=replay(args.pdf,omit_reference_at=args.omit_reference_at);args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='sections'},ensure_ascii=False,indent=2))
