"""Review one known DTP teaching-scope false stop against supplied original text."""
from pathlib import Path
from copy import deepcopy
import hashlib,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from term_explainer.full_job import RecordedClient,fingerprint,deliver
from term_explainer.deepseek import DeepSeekClient
from tools.read_term_sections import load_json,atomic_write
from tools.run_term_explainer import summary


def main():
    folder=Path(__file__).resolve().parents[1]/'.superpowers/sdd/2026-10-18-personal-term-explainer-phase1/live/dtp-user-pdf/dtp-multi-literature-run'
    lock=(folder/'job.lock').open('x',encoding='utf-8')
    try:
        state=load_json(folder/'job.json',16777216);payload=load_json(folder/'input.json')
        expected='样本量、缺失数据处理、block 大小与特质数等适用条件未系统给出。'
        bundle=state['evidence']
        if (state['input_hash']!=fingerprint(payload) or state['stage']!='needs_sources'
                or state['literature_review']['questions']!=[expected] or bundle['reported_gaps']!=[expected]
                or bundle['missing_modules'] or bundle['unresolved_claims'] or bundle['questions'] or state.get('applicability_scope_review')):
            raise ValueError('Only the inspected single scope false stop is eligible')
        text=state['selected_source']['text']
        anchors=['grouped into MFC blocks','DTP Matching','Suppose that MFC data are available']
        positions=[]
        for phrase in anchors:
            start=text.index(phrase);positions.append(dict(source_id=state['selected_source']['id'],start=start,end=min(len(text),start+800)))
        audit=dict(original_input_hash=state['input_hash'],source_hash=hashlib.sha256(text.encode()).hexdigest(),
            exact_question=expected,source_positions=positions,
            decision='Source specifies input format and matching construction; a systematic minimum-N/missing-data/performance boundary is not required for a no-execution concept explanation. Do not invent these boundaries or claim validation.',
            human_scientific_signoff='pending',new_model_calls_for_review=0)
        atomic_write(folder/'before-applicability-scope-job.json',state)
        atomic_write(folder/'applicability-scope-review.json',audit)
        bundle.setdefault('research_questions',[]).append(dict(text=expected,reason=audit['decision'],fact_verified=False))
        bundle.update(reported_gaps=[],status='ready_for_explanation',can_generate=True)
        state.update(stage='lesson',applicability_scope_review=audit)
        def save(value):atomic_write(folder/'job.json',value);atomic_write(folder/'report.json',summary(value))
        save(state)
        client=RecordedClient(DeepSeekClient(max_calls=2,max_tokens=16384,timeout=180),state,folder/'responses',save)
        deliver(state,payload,client,save,folder,external_qa=True)
        print(json.dumps(summary(state),ensure_ascii=False,indent=2))
    finally:lock.close();(folder/'job.lock').unlink()


if __name__=='__main__':main()
