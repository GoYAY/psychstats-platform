"""Whole-document adapter for the existing bounded, source-first literature pipeline."""
from copy import deepcopy
from .contract import validate_request
from .pipeline import prepare_evidence


def reconcile_truncation(state,input_hash):
    """Explicit, one-time recovery of a known received length stop, never a timeout."""
    if state.get('input_hash')!=input_hash or not input_hash or state.get('stage')!='evidence':
        raise ValueError('Truncation recovery needs the unchanged evidence-stage input')
    if state.get('truncation_recovery'):raise ValueError('Truncation recovery already used')
    event=state.get('events',[])[-1] if state.get('events') else {}
    if event.get('error_code')!='model_truncated' or event.get('api_calls')!=1 or event.get('metrics',{}).get('finish_reason')!='length':
        raise ValueError('Only a received length stop can be reviewed; unknown transport errors cannot retry')
    state['truncation_recovery']=dict(reason='Received length stop; compact analysis contract after local review',original_request_hash=event.get('request_hash'),input_hash=input_hash)
    state.setdefault('stage_attempts',{})['evidence']=1
    # Preserve the actual billed usage that was available despite rejected content.
    if event.get('metrics',{}).get('usage'):event['usage']=deepcopy(event['metrics']['usage'])


def create_enrichment(state,payload,supplements):
    from .full_job import fingerprint
    if state.get('stage')!='complete' or state.get('input_hash')!=fingerprint(payload):
        raise ValueError('Enrichment requires an unchanged complete original task')
    new=deepcopy(state);updated=deepcopy(payload)
    limit=sum(len(p['text']) for b in state['lesson']['blocks'] for p in b['paragraphs'])
    updated['multi_literature']=True
    updated['request'].update(max_body_chars=limit,optional_reference_reads=True)
    updated['request']['sources']=deepcopy(updated['request'].get('sources',[]))+deepcopy(supplements)
    new.update(stage='evidence',input_hash=fingerprint(updated),events=[],prior_events=deepcopy(state.get('events',[])),
        stage_attempts={},enrichment_origin=dict(original_input_hash=state['input_hash'],original_lesson_hash=fingerprint(state['lesson']),body_char_limit=limit))
    for key in ('last_error','output_page'):new.pop(key,None)
    return new,updated


def compile_multi_evidence(state,payload,client,save,*,attempt=0):
    from .full_job import RecordedClient,JobError
    primary=deepcopy(state['selected_source'])
    # Bibliography is a locator only. Appending preserves all existing body offsets.
    citations=[];mapping=[]
    for section in state['reading']['sections']:
        if section['title'] not in {'References','参考文献'}:continue
        raw=payload['source']['text'][section['start']:section['end']]
        citations.append(raw);mapping.append(dict(original_start=section['start'],original_end=section['end']))
    if citations:
        locator_start=len(primary['text'])
        primary['text']+='\n\n'+'\n\n'.join(citations)
        primary.setdefault('locator_only_ranges',[]).append(dict(start=locator_start,end=len(primary['text'])))
        if len(primary['text'])>60000:raise JobError('source_budget_exceeded','主文与引文目录超过阅读范围，未截断。')
    sources=[primary]
    original_id=payload['source']['id']
    for source in [*state.get('reader_sources',[]),*payload['request'].get('sources',[])]:
        if source['id'] in {primary['id'],original_id} or any(s['id']==source['id'] for s in sources):continue
        sources.append(deepcopy(source))
    from .literature import deduplicate_sources
    primary_work=deduplicate_sources([primary])[0]['work_id']
    extra_works={s['work_id'] for s in deduplicate_sources(sources) if s['work_id']!=primary_work}
    if len(extra_works)>3:raise JobError('reference_limit','补充文献超过本轮三篇范围。')
    request=validate_request(dict(payload['request'],sources=sources,optional_reference_reads=True,max_reference_reads=3-len(extra_works)))
    if isinstance(client,RecordedClient):
        client.phase=f'literature:{attempt}'
        client.hint=''
    reply=prepare_evidence(request,client)
    state['literature_review']=dict(action=reply.action,questions=reply.questions,bibliography_mapping=mapping,
        policy=dict(max_additional_reads=3,max_reference_depth=1),human_review='pending')
    if reply.evidence:
        reply.evidence['multi_literature']=True
        state['evidence']=reply.evidence
        state['reader_sources']=[s for s in reply.evidence['sources'] if s['scope']!='metadata']
    if reply.action!='ready_for_explanation':
        state['stage']=reply.action;save(state)
        raise JobError(reply.action,'多文献整合保留了具体未解决问题，未生成无依据科普。')
    state['stage']='lesson';save(state)
