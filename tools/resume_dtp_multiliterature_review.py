"""Source-bound local review of the saved DTP analysis; never rereads it by API."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import hashlib,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from term_explainer.full_job import RecordedClient,fingerprint,deliver
from term_explainer.expansion import compile_multi_evidence
from term_explainer.evidence import context_spans
from term_explainer.deepseek import DeepSeekClient,ModelReply
from tools.read_term_sections import load_json,atomic_write
from tools.run_term_explainer import summary


def main():
    root=Path(__file__).resolve().parents[1]
    folder=root/'.superpowers/sdd/2026-10-18-personal-term-explainer-phase1/live/dtp-user-pdf/dtp-multi-literature-run'
    lock=(folder/'job.lock').open('x',encoding='utf-8')
    try:
        state=load_json(folder/'job.json',16777216);payload=load_json(folder/'input.json')
        if state['stage']!='evidence' or state['input_hash']!=fingerprint(payload):raise ValueError('Unchanged evidence task required')
        if state.get('analysis_local_review'):raise ValueError('Local review already applied; do not duplicate requests')
        saved=[e for e in state['events'] if e.get('phase')=='literature:1' and e.get('status')=='response_received']
        if len(saved)!=1:raise ValueError('Exactly one completed saved analysis expected')
        event=saved[0];cache_file=folder/'responses'/(event['request_hash']+'.json');cache=load_json(cache_file)
        if cache['request_hash']!=event['request_hash']:raise ValueError('Cache identity mismatch')
        original=json.loads(cache['reply']['content']);reviewed=deepcopy(original)
        source=state['selected_source'];cut=len(source['text'])
        bib=next(s for s in state['reading']['sections'] if s['title']=='References')
        text=source['text']+'\n\n'+payload['source']['text'][bib['start']:bib['end']]
        span=next(s for s in context_spans(source['id'],text) if s['id']==source['id']+'#c0029')
        # Inspected conclusion passage ends exactly here; bibliography suffix is not evidence.
        conclusion=text[span['start']:cut]
        if not (span['start']<cut<span['end'] and 'additional research is needed' in conclusion):raise ValueError('Reviewed passage changed')
        replacements=[]
        for field,index in [('reading_notes',0),('claims',10),('synthesis',0)]:
            item=reviewed[field][index]
            for i,ref in enumerate(item['evidence']):
                if ref==dict(source_id=source['id'],span_id='c0029'):
                    item['evidence'][i]=dict(source_id=source['id'],start=span['start'],end=cut)
                    replacements.append(dict(field=field,index=index,original=ref,replacement=item['evidence'][i]))
        if len(replacements)!=3:raise ValueError('Expected exactly the three inspected mixed-span citations')
        discarded=[r for r in reviewed['source_relations'] if r['type']=='cites']
        if {(r['source'],r['target']) for r in discarded}!={('dtp-user-paper-appendix','brown2011'),('nie2024','brown2011')}:raise ValueError('Unexpected citation-edge review scope')
        reviewed['source_relations']=[r for r in reviewed['source_relations'] if r not in discarded]
        for item in reviewed['synthesis']:
            item['related_source_ids']=[target for target in item['related_source_ids'] if any({r['source'],r['target']}=={item['source_id'],target} for r in reviewed['source_relations'])]
        audit=dict(input_hash=state['input_hash'],response_hash=hashlib.sha256(cache_file.read_bytes()).hexdigest(),
            original_analysis_hash=fingerprint(original),reviewed_analysis_hash=fingerprint(reviewed),
            precise_body_references=replacements,unaccepted_citation_edges=discarded,
            decision='Retain original factual claims; clip three inspected body/bibliography mixed spans; do not certify unregistered citation edges. Research-gap purpose goes through a separate model review.',new_api_calls_for_replay=0)
        atomic_write(folder/'analysis-review.json',audit)
        atomic_write(folder/'before-analysis-review-job.json',state)
        def save(value):atomic_write(folder/'job.json',value);atomic_write(folder/'report.json',summary(value))
        class ReviewedClient(RecordedClient):
            first=True
            def generate(self,messages,*args,**kwargs):
                if self.first:
                    self.first=False
                    if 'reading_notes' not in messages[0]['content']:raise ValueError('Expected analysis replay only')
                    return ModelReply(json.dumps(reviewed,ensure_ascii=False),cache['reply']['model'],{},'stop')
                return super().generate(messages)
        client=ReviewedClient(DeepSeekClient(max_calls=2,max_tokens=16384,timeout=180),state,folder/'responses',save)
        state['analysis_local_review']=audit;save(state)
        compile_multi_evidence(state,payload,client,save,attempt=1)
        deliver(state,payload,client,save,folder,external_qa=True)
        print(json.dumps(summary(state),ensure_ascii=False,indent=2))
    finally:lock.close();(folder/'job.lock').unlink()


if __name__=='__main__':main()
