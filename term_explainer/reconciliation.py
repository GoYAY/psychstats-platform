"""Explicit local source-review decisions; no network and no raw response edits.

This is a developer reconciliation path, not an automatic semantic classifier or
a commercial authorization boundary. A review can dismiss only exact recorded
scope observations. Bibliographic identity mismatches remain blocked.
"""
from copy import deepcopy
import hashlib
import json

from .deepseek import ModelReply
from .evidence import resolve_reference
from .full_job import fingerprint
from .section_quality import identity_context
from .section_reading import read_next_section


def apply_section_scope_review(state,payload,response,review):
    """Return a validated new state by replaying one reviewed saved model response.

    Caller persists the original state/review before replacing its active state.
    Neither input objects nor cache files are mutated. No provider is instantiated.
    """
    if not isinstance(review,dict) or review.get('decision')!='section_scope_not_anchor_conflict':
        raise ValueError('An explicit scoped review is required')
    for key,limit in [('reviewer',100),('reason',2000)]:
        if not isinstance(review.get(key),str) or not review[key].strip() or len(review[key])>limit:
            raise ValueError('Review author and reason are required')
    if state.get('input_hash')!=fingerprint(payload): raise ValueError('Task input changed')
    reading=state['reading']; source=payload['source']
    if state['stage']!='needs_disambiguation' or reading['status']!='needs_disambiguation':
        raise ValueError('Only a stopped ambiguous section can be reconciled')
    index=reading['next_section']
    if type(index) is not int or not 0<=index<len(reading['sections']) or len(reading['readings'])!=index:
        raise ValueError('Invalid section progress')
    section=reading['sections'][index]
    if (reading['source_hash']!=hashlib.sha256(source['text'].encode()).hexdigest()
            or reading['term_hash']!=hashlib.sha256(json.dumps(payload['request']['term'],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
            or review.get('source_hash')!=reading['source_hash'] or review.get('term_hash')!=reading['term_hash']
            or review.get('section_id')!=section['id'] or review.get('response_hash')!=fingerprint(response)):
        raise ValueError('Review is not bound to this term, source, section and response')
    identity_context(reading.get('identity_review'),source)
    event=next((e for e in reversed(state['events']) if e.get('request_hash')==review.get('request_hash')),None)
    if (event is None or event.get('status')!='response_received'
            or not event.get('phase','').startswith('section:'+section['id']+':')
            or response.get('request_hash')!=event['request_hash']):
        raise ValueError('Review must identify the completed section request')
    raw=ModelReply(**response['reply'])
    if raw.finish_reason!='stop' or raw.usage!=event.get('usage'):
        raise ValueError('Only a complete saved response can be replayed')
    data=json.loads(raw.content)
    conflicts=data.get('anchor_conflicts')
    if (not isinstance(conflicts,list) or not conflicts or conflicts!=reading.get('questions')
            or review.get('dismissed_conflicts')!=conflicts):
        raise ValueError('Review does not cover exactly the recorded observations')
    # Never dismiss an identity mismatch merely because a local reviewer chose scope.
    for item in [data,*data.get('reading_notes',[])]:
        if 'identity_check' in item and item['identity_check'].get('status')!='matches':
            raise ValueError('Bibliographic identity uncertainty cannot be dismissed by a scope review')
    refs=review.get('evidence')
    if not isinstance(refs,list) or not 1<=len(refs)<=4: raise ValueError('Review needs located section evidence')
    refs=[resolve_reference(ref,[source]) for ref in refs]
    if any(r['source_id']!=source['id'] or not section['start']<=r['start']<r['end']<=section['end'] for r in refs):
        raise ValueError('Review evidence must be inside the exact section')
    if type(reading['reserved_calls']) is not int or reading['reserved_calls']<1:
        raise ValueError('Missing original paid request reservation')
    new=deepcopy(state); record=deepcopy(review)
    record.update(evidence=refs,previous_error=deepcopy(state.get('last_error')),
                  previous_reading_error=reading.get('last_error'),new_api_calls=0,
                  semantic_claims_verified=False)
    # This review changes only a scope classification, never scientific claims.
    data['anchor_conflicts']=[]
    corrected=ModelReply(json.dumps(data,ensure_ascii=False),raw.model,raw.usage,raw.finish_reason)
    class SavedResponseOnly:
        def __init__(self): self.used=False
        def generate(self,messages,*args,**kwargs):
            if self.used: raise ValueError('Only one saved response is authorized for replay')
            self.used=True
            return corrected
    replay=SavedResponseOnly(); current=new['reading']
    current.update(status='reading',reserved_calls=current['reserved_calls']-1)
    read_next_section(current,payload['request'],source,replay,context_limit=64000)
    if not replay.used or current['next_section']!=index+1:
        raise ValueError('Saved response failed normal section validation')
    if current['reserved_calls']!=reading['reserved_calls']:
        raise ValueError('Replay changed the original call reservation')
    current['readings'][-1]['scope_review']=record
    for key in ('questions','last_error'): current.pop(key,None)
    new.setdefault('reconciliations',[]).append(record)
    new.pop('last_error',None); new['stage']='reading'
    return new
