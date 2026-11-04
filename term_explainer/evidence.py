"""Stable source spans and identity-preserving prompt preparation."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, is_dataclass
import re


def segment_source(source_id: str, text: str, chunk_size: int = 1600) -> list[dict]:
    if not isinstance(text, str) or not isinstance(chunk_size, int) or chunk_size < 1:
        raise ValueError('invalid source segmentation input')
    spans = []
    for match in re.finditer(r'[^\n]+', text):
        if not match.group().strip():
            continue
        for start in range(match.start(), match.end(), chunk_size):
            end = min(start + chunk_size, match.end())
            spans.append(dict(id=f'{source_id}#p{len(spans):04d}', start=start,
                              end=end, text=text[start:end]))
    return spans


def context_spans(source_id: str, text: str, chunk_size: int = 1600) -> list[dict]:
    """Pack wrapped PDF lines without changing their characters or source positions.

    Versioned c IDs coexist with legacy p IDs. Page labels remain in the original
    source but are never standalone evidence units in the model context.
    """
    if not isinstance(text, str) or type(chunk_size) is not int or chunk_size < 1:
        raise ValueError('invalid context segmentation input')
    spans = []
    start = end = None
    def flush():
        nonlocal start, end
        if start is not None:
            spans.append(dict(id=f'{source_id}#c{len(spans):04d}', start=start,
                              end=end, text=text[start:end]))
        start = end = None
    for match in re.finditer(r'[^\n]+', text):
        line = match.group()
        if not line.strip():
            continue
        if re.fullmatch(r'=+\s*PDF PAGE\s+\d+\s*=+', line.strip()):
            flush()
            continue
        if start is not None and match.end() - start > chunk_size:
            flush()
        for pos in range(match.start(), match.end(), chunk_size):
            if start is None:
                start = pos
            end = min(pos + chunk_size, match.end())
            if end - start >= chunk_size:
                flush()
    flush()
    return spans


def locator_overlap(source,start,end):
    return any(start<r['end'] and end>r['start'] for r in source.get('locator_only_ranges',[]))


def teaching_spans(source):
    text=source['text'];cuts=sorted({0,len(text),*(p[k] for p in source.get('locator_only_ranges',[]) for k in ('start','end'))})
    result=[]
    for start,end in zip(cuts,cuts[1:]):
        for span in context_spans(source['id'],text[start:end]):
            span.update(id=f"{source['id']}#c{len(result):04d}",start=span['start']+start,end=span['end']+start)
            result.append(dict(span,evidence_eligible=not locator_overlap(source,span['start'],span['end'])))
    return result


def resolve_reference(reference: dict, sources: list[dict], *, allow_locator=False) -> dict:
    if not isinstance(reference, dict):
        raise ValueError('reference must be an object')
    source = next((s for s in sources if s['id'] == reference.get('source_id')), None)
    if source is None or source.get('scope') == 'metadata':
        raise ValueError('unknown or unreadable evidence source')
    if 'span_id' in reference:
        if not isinstance(reference['span_id'], str):
            raise ValueError('invalid evidence span ID')
        if re.fullmatch(r'[cp]\d{4}',reference['span_id']):
            reference=dict(reference,span_id=source['id']+'#'+reference['span_id'])
        spans=teaching_spans(source) if reference['span_id'].startswith(source['id'] + '#c') else segment_source(source['id'],source['text'])
        span = next((s for s in spans
                     if s['id'] == reference['span_id']), None)
        if span is None:
            raise ValueError('unknown evidence span')
        start, end = span['start'], span['end']
    else:
        start, end = reference.get('start'), reference.get('end')
    if (type(start) is not int or type(end) is not int
            or not 0 <= start < end <= len(source['text'])
            or not source['text'][start:end].strip()):
        raise ValueError('evidence reference is outside source text')
    if re.fullmatch(r'=+\s*PDF PAGE\s+\d+\s*=+', source['text'][start:end].strip()):
        raise ValueError('a page marker is not evidence')
    if not allow_locator and locator_overlap(source,start,end):
        raise ValueError('bibliography locator cannot support a teaching claim')
    return dict(source_id=source['id'], start=start, end=end)


def prepare_context(request) -> dict:
    value = asdict(request) if is_dataclass(request) else deepcopy(request)
    term = value['term']
    anchor = dict(term=term.get('zh', ''), english=term.get('en', ''), definition=term.get('definition', ''))
    anchor.update({key: deepcopy(term[key]) for key in ('author', 'year', 'doi') if key in term})
    def summaries(name):
        return [{key: deepcopy(item[key]) for key in ('id', 'zh', 'en', 'aliases', 'kind') if key in item}
                for item in value.get(name, [])]
    return dict(anchor=anchor,
                question=value.get('question', ''),
                sources=[dict(id=s['id'], title=s.get('title', ''), scope=s['scope'],
                              authors=s.get('authors', []), year=s.get('year'), doi=s.get('doi', ''),
                              retrieved_title=s.get('retrieved_title', ''), retrieved_url=s.get('retrieved_url', ''),
                              scope_basis=s.get('scope_basis', 'user_selected_text'),
                              technical_evidence_eligible=s.get('technical_evidence_eligible', s['scope'] in {'excerpt','full_text'}),
                              origin=s.get('origin', 'user'), references=s.get('references', []),
                              spans=teaching_spans(s)) for s in value['sources']],
                catalog=summaries('catalog'), known_terms=summaries('known_terms'))


def prepare_reading_context(request,memory,document_identity):
    """Bounded per-unit reading context: no catalog, no known-term inventory,
    no visual specs, no history claims.  Field order is fixed so the request
    prefix stays stable across units."""
    value = asdict(request) if is_dataclass(request) else deepcopy(request)
    term = value['term']
    anchor = dict(term=term.get('zh', ''), english=term.get('en', ''), definition=term.get('definition', ''))
    anchor.update({key: deepcopy(term[key]) for key in ('author', 'year', 'doi') if key in term})
    return dict(anchor=anchor,
                question=value.get('question', ''),
                reading_policy=dict(network_allowed=request.network_allowed,
                    max_reference_reads=request.max_reference_reads,
                    already_read_source_ids=[s['id'] for s in request.sources if s['scope']!='metadata']),
                document_identity=deepcopy(document_identity) if document_identity else None,
                reading_memory=deepcopy(memory) if memory else {},
                sources=[dict(id=s['id'], title=s.get('title', ''), scope=s['scope'],
                              scope_basis=s.get('scope_basis', 'user_selected_text'),
                              technical_evidence_eligible=s.get('technical_evidence_eligible', s['scope'] in {'excerpt','full_text'}),
                              origin=s.get('origin', 'user'), references=s.get('references', []),
                              spans=teaching_spans(s)) for s in value['sources']])


def resolve_term(text: str, catalog: list[dict], current_id: str):
    phrase = text.strip().casefold()
    matches = [t for t in catalog if any(isinstance(n, str) and n.strip().casefold() == phrase
               for n in [t.get('zh'), t.get('en'), *t.get('aliases', [])])]
    if len(matches) != 1 or matches[0]['id'] == current_id:
        return None
    return deepcopy(matches[0])
