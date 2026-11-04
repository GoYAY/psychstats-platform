"""Checkpointable one-paper reading: section text + bounded rolling context.

Headings are explicit, verified offsets from document structure, not percentages.
The complete original lives locally. Summaries never replace its evidence spans.
"""
from copy import deepcopy
import hashlib
import json

from .contract import validate_request, _string
from .literature import _sources, assemble_evidence_bundle
from .pipeline import _analyse
from .section_quality import (validate_identity_review, identity_context, condition_memory,
                              citation_warnings)


def _fingerprint(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def create_reading_state(request, source, headings, *, max_calls=0, identity_review=None):
    source = _sources([source])[0]
    text = source['text']
    if not text or len(text) > 120000 or type(max_calls) is not int or max_calls < 0:
        raise ValueError('invalid paper or reading budget')
    if not isinstance(headings, list) or not headings:
        raise ValueError('verified section headings are required')
    previous = -1
    for heading in headings:
        title, start = heading['title'], heading['start']
        if (type(start) is not int or start <= previous or not 0 <= start < len(text)
                or not isinstance(title, str) or not title.strip()
                or not text.startswith(title, start)
                or text[text.rfind('\n',0,start)+1:start].strip()):
            raise ValueError('section boundary must match the actual heading in order')
        previous = start
    boundaries = deepcopy(headings)
    if boundaries[0]['start']:
        boundaries.insert(0, dict(title='首个标题前的内容', start=0))
    sections = [dict(id=f'section-{i+1:03d}', title=heading['title'], start=heading['start'],
                     end=boundaries[i+1]['start'] if i+1 < len(boundaries) else len(text),
                     **({'role':'front_matter'} if heading.get('role')=='front_matter' else {}))
                for i, heading in enumerate(boundaries)]
    from .reading_plan import build_units,validate_units
    units = build_units(sections)
    validate_units(units, sections, text)
    return dict(paper_id=source['id'], source_hash=_fingerprint(text),
        term_hash=_fingerprint(json.dumps(request['term'],ensure_ascii=False,sort_keys=True)),
        sections=units, section_index=sections, reading_plan_version=units[0]['plan_version'],
        next_section=0, readings=[], rolling_summary='',
        max_calls=max_calls, reserved_calls=0, status='reading', can_generate=False,
        requires_semantic_review=True, identity_review=validate_identity_review(identity_review,source))


def read_next_section(state, request, source, client, *, checkpoint=None, context_limit=12000):
    """Read at most one section. Persist reservation before HTTP via checkpoint.

    An interrupted or failed attempt cannot silently be resumed/retried. A fresh
    client does not reset the persistent call reservation in state.
    """
    if not request.get('network_allowed', True):
        raise ValueError('model access is not allowed for this request')
    if (state['source_hash'] != _fingerprint(source['text']) or state['paper_id'] != source['id']
            or state['term_hash'] != _fingerprint(json.dumps(request['term'],ensure_ascii=False,sort_keys=True))):
        raise ValueError('source or original term changed; cannot resume this checkpoint')
    if state['status'] in ('in_flight','failed_requires_review','needs_disambiguation'):
        raise ValueError('inspect and reconcile this attempt before resuming')
    document_identity = identity_context(state.get('identity_review'),source)
    conditions = condition_memory(state,source)
    if state['next_section'] >= len(state['sections']):
        return state
    section = state['sections'][state['next_section']]
    if section['end'] - section['start'] > 60000:
        state['status'] = 'needs_subsections'
        return state
    if state['reserved_calls'] >= state['max_calls']:
        state['status'] = 'needs_budget'
        return state
    selected = dict(source, text=source['text'][section['start']:section['end']], scope='excerpt',
                    scope_basis='verified_section:' + section['title'])
    payload = dict(request, sources=[selected])
    validated = validate_request(payload)
    memory = dict(summary=state['rolling_summary'], role='unverified_context_not_a_source',
                  current_section=section['title'], completed_sections=[r['section_id'] for r in state['readings']],
                  key_conditions=conditions,
                  condition_coverage='legacy_unrecorded' if any('key_conditions' not in r for r in state['readings']) else 'recorded_not_verified')
    if state.get('source_set_context') is not None:memory['source_set']=deepcopy(state['source_set_context'])
    if type(context_limit) is not int or context_limit < 1:
        raise ValueError('invalid retained-context limit')
    if len(json.dumps(memory,ensure_ascii=False)) > context_limit:
        state['status'] = 'needs_context_selection'
        if checkpoint:
            checkpoint(state)
        return state
    state.update(status='in_flight', reserved_calls=state['reserved_calls']+1)
    if checkpoint:
        checkpoint(state)
    try:
        usage = []
        analysis = _analyse(validated, client, usage, reading_memory=memory, document_identity=document_identity)
        if analysis.get('analysis_contract'):
            state.setdefault('analysis_contracts',{})[section['id']]=deepcopy(analysis['analysis_contract'])
        summary = _string(analysis.get('rolling_summary'), 'rolling_summary', maximum=2000)
        if len(analysis['claims']) > 8 or any(len(c['evidence']) > 2 for c in analysis['claims']):
            raise ValueError('section evidence output exceeded its bounds')
        bundle = assemble_evidence_bundle(memory_anchor(validated), [selected], analysis['claims'],
                                          analysis['source_relations'])
        def original_positions(value):
            if isinstance(value, list):
                return [original_positions(v) for v in value]
            if isinstance(value, dict):
                result = {key:original_positions(v) for key,v in value.items()}
                if result.get('source_id') == source['id'] and 'start' in result and 'end' in result:
                    result.update(start=result['start']+section['start'],end=result['end']+section['start'])
                return result
            return value
        reading = original_positions(dict(section_id=section['id'],title=section['title'],
            reading_notes=analysis['reading_notes'],claims=bundle['claims'],
            rolling_summary=summary,reported_gaps=analysis['missing_evidence'],
            reference_candidates=analysis['reference_candidates'],usage=usage,
            key_conditions=analysis['key_conditions'],identity_observations=analysis.get('identity_observations',[])))
        reading['citation_warnings'] = citation_warnings(source,reading['claims'],
                                                        start=section['start'],end=section['end'])
        if analysis.get('analysis_contract'):reading['analysis_contract']=deepcopy(analysis['analysis_contract'])
        if analysis['anchor_conflicts']:
            state.update(status='needs_disambiguation',questions=analysis['anchor_conflicts'])
            return state
        state['readings'].append(reading)
        state.update(rolling_summary=summary, next_section=state['next_section']+1,
                     status='read_all_requires_review' if state['next_section']+1 == len(state['sections']) else 'reading')
        return state
    except Exception as error:
        state.update(status='failed_requires_review',last_error=getattr(error,'code','invalid_section_analysis'))
        audit=getattr(error,'analysis_contract',None) or state.get('analysis_contracts',{}).get(section['id'])
        if audit:
            state['analysis_contract_failure']=dict(section_id=section['id'],**deepcopy(audit))
            error.analysis_contract=deepcopy(audit)
        raise
    finally:
        if checkpoint:
            checkpoint(state)


def memory_anchor(request):
    from .evidence import prepare_context
    return prepare_context(dict(term=request.term,sources=[],catalog=[],known_terms=[]))['anchor']
