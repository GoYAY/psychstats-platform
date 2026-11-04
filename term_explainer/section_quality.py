"""Local provenance and review helpers. No network or semantic auto-approval."""
from copy import deepcopy
import hashlib
import json
import re

from .contract import _array, _identifier, _object, _string
from .evidence import context_spans, resolve_reference


def validate_identity_review(review, source):
    """Validate an explicit local review, never infer verification from upload origin."""
    if review is None:
        return None
    _object(review, 'identity_review')
    if len(json.dumps(review, ensure_ascii=False)) > 12000:
        raise ValueError('identity review is too large')
    bibliography = {k: deepcopy(source.get(k, [] if k == 'authors' else None if k == 'year' else ''))
                    for k in ('title','authors','year','doi')}
    digest = hashlib.sha256(source['text'].encode('utf-8')).hexdigest()
    if (review.get('status') != 'matches' or review.get('source_id') != source['id']
            or review.get('source_hash') != digest or review.get('bibliography') != bibliography):
        raise ValueError('identity review does not match this original source')
    reviewer = _string(review.get('reviewer'), 'identity reviewer', maximum=100)
    refs = [resolve_reference(r, [source]) for r in _array(review.get('evidence'), 'identity evidence', 3)]
    if not refs or any(r['source_id'] != source['id'] for r in refs):
        raise ValueError('identity review needs located original evidence')
    # Require a complete title or identifier in the cited text; offsets alone are insufficient.
    normalize = lambda value: re.sub(r'\s+', '', value).casefold()
    needles = [normalize(bibliography[k]) for k in ('title','doi') if bibliography[k]]
    if not needles or not any(needle in normalize(source['text'][r['start']:r['end']])
                              for needle in needles for r in refs):
        raise ValueError('identity evidence does not contain the reviewed title or DOI')
    return dict(status='matches',source_id=source['id'],source_hash=digest,
                bibliography=bibliography,reviewer=reviewer,evidence=refs)


def identity_context(review, source):
    checked = validate_identity_review(review, source)
    # Full-document review offsets are local audit data, not current-section citations.
    if checked:
        checked.pop('evidence')
    return dict(checked, role='document_identity_only_not_method_evidence') if checked else dict(
        status='not_reviewed',source_id=source['id'],role='document_identity_only_not_method_evidence')


def condition_memory(state, source):
    """Rebuild append-only conditions from section records, not rewritten summaries."""
    if hashlib.sha256(source['text'].encode('utf-8')).hexdigest() != state['source_hash']:
        raise ValueError('condition source changed')
    result = []
    for i, reading in enumerate(state['readings']):
        section = state['sections'][i]
        if reading['section_id'] != section['id']:
            raise ValueError('condition section order mismatch')
        seen = set()
        for item in _array(reading.get('key_conditions', []), 'saved key conditions', 4):
            _object(item, 'saved condition')
            key = _identifier(item.get('id'), 'condition.id')
            if key in seen:
                raise ValueError('duplicate condition id')
            seen.add(key)
            statement = _string(item.get('statement'), 'condition.statement', maximum=400)
            refs = [resolve_reference(r, [source]) for r in _array(item.get('evidence'), 'condition.evidence', 2)]
            if not refs or any(r['source_id'] != source['id'] or not
                    section['start'] <= r['start'] < r['end'] <= section['end'] for r in refs):
                raise ValueError('condition evidence must be inside its original section')
            result.append(dict(id=section['id']+'--'+key,statement=statement,evidence=refs,
                               content_verified=False))
    return result


def recall_conditions(state, source, ids, *, max_chars=6000):
    """Return selected actual evidence for later synthesis; never cite the summary."""
    if type(max_chars) is not int or max_chars < 1:
        raise ValueError('invalid recall budget')
    requested = _array(ids, 'condition IDs', 20)
    if any(not isinstance(i, str) for i in requested) or len(set(requested)) != len(requested):
        raise ValueError('invalid condition IDs')
    known = {item['id']:item for item in condition_memory(state, source)}
    if any(i not in known for i in requested):
        raise ValueError('unknown condition ID')
    result = []
    for key in requested:
        for ref in known[key]['evidence']:
            result.append(dict(ref,condition_id=key,excerpt=source['text'][ref['start']:ref['end']],
                               content_verified=False))
    if sum(len(r['excerpt']) for r in result) > max_chars:
        raise ValueError('selected original evidence exceeds recall budget; select fewer conditions')
    return result


def citation_warnings(source, claims, *, start, end):
    """Flag unfinished span boundaries, not entailment. Never expand saved citations."""
    spans = context_spans(source['id'], source['text'][start:end])
    for span in spans:
        span['start'] += start
        span['end'] += start
    def unfinished(span):
        return bool(span['text'].strip()) and span['text'].rstrip()[-1] not in '.!?。！？;；:：”’"\')）'
    warnings = []
    for claim in claims:
        positions = {(r['start'], r['end']) for r in claim['evidence']}
        for i, span in enumerate(spans):
            if (span['start'],span['end']) not in positions:
                continue
            neighbors = []
            if i and unfinished(spans[i-1]):
                neighbors.append(('preceding_span_may_complete_sentence',spans[i-1]))
            if i+1 < len(spans) and unfinished(span):
                neighbors.append(('following_span_may_complete_sentence',spans[i+1]))
            for code, neighbor in neighbors:
                if (neighbor['start'],neighbor['end']) not in positions:
                    warnings.append(dict(code=code,claim_id=claim['id'],requires_semantic_review=True,
                        adjacent_evidence=dict(source_id=source['id'],start=neighbor['start'],end=neighbor['end'])))
    return warnings
