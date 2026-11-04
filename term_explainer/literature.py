"""Pure literature workflow rules; no networking or model calls happen here.

An anchor describes the user's intended concept. It is not replaced by search.
Located excerpts prove traceability, not that an interpretation is true.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
import re


@dataclass(frozen=True)
class LiteraturePolicy:
    max_search_queries: int = 2
    max_automatic_reads: int = 6
    max_reference_reads: int = 3
    max_reference_depth: int = 1

    def __post_init__(self):
        for key, value in vars(self).items():
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f'{key} must be a non-negative integer')


DEFAULT_POLICY = LiteraturePolicy()
SCOPES = frozenset({'metadata', 'abstract', 'excerpt', 'full_text'})
MODULES = frozenset({'definition', 'method', 'application', 'validation', 'limitation', 'background'})
RELATIONS = frozenset({'cites', 'extends', 'compares', 'validates', 'contradicts', 'background'})


def _text(value, field, *, required=False):
    if not isinstance(value, str) or (required and not value.strip()):
        raise ValueError(f'{field} must be a non-empty string' if required else f'{field} must be a string')
    return value


def _anchor(value):
    if not isinstance(value, dict):
        raise ValueError('anchor must be an object')
    for key in ('term', 'definition', 'english', 'author', 'doi'):
        if key in value:
            _text(value[key], f'anchor.{key}')
    if not (value.get('term', '').strip() or value.get('definition', '').strip()):
        raise ValueError('provide a term or a definition')
    return deepcopy(value)


def _doi(value):
    text = _text(value or '', 'doi').strip().lower()
    text = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi\s*:\s*)', '', text)
    if text and not re.fullmatch(r'10\.\d{4,9}/\S+', text):
        raise ValueError('doi must be a DOI or DOI URL')
    return text


def _sources(records):
    if not isinstance(records, list):
        raise ValueError('sources must be an array')
    result, seen = [], set()
    for value in records:
        if not isinstance(value, dict):
            raise ValueError('source must be an object')
        item = deepcopy(value)
        source_id = _text(item.get('id'), 'source.id', required=True)
        if source_id in seen:
            raise ValueError(f'duplicate source id: {source_id}')
        seen.add(source_id)
        _text(item.get('title', ''), 'source.title')
        _text(item.get('text', ''), 'source.text')
        item.setdefault('text', '')
        item.setdefault('scope', 'metadata')
        item.setdefault('origin', 'user')
        if item['origin'] not in {'user', 'search', 'reference'}:
            raise ValueError('unknown source origin')
        if not isinstance(item['scope'], str) or item['scope'] not in SCOPES:
            raise ValueError('unknown source scope')
        if 'technical_evidence_eligible' in item and type(item['technical_evidence_eligible']) is not bool:
            raise ValueError('technical evidence eligibility must be boolean')
        if item['scope'] == 'metadata' and item['text'].strip():
            raise ValueError('metadata-only sources must not masquerade as readable text')
        if item['scope'] != 'metadata' and not item['text'].strip():
            raise ValueError('readable scope requires actual text')
        ranges=item.get('locator_only_ranges',[])
        if not isinstance(ranges,list):raise ValueError('invalid locator ranges')
        for part in ranges:
            if (not isinstance(part,dict) or type(part.get('start')) is not int or type(part.get('end')) is not int
                    or not 0<=part['start']<part['end']<=len(item['text'])):
                raise ValueError('invalid locator range')
        _doi(item.get('doi', ''))
        result.append(item)
    return result


def _digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()

def work_identity(source):
    """Never treat an unresolved upload label/filename as a bibliographic ID."""
    doi=_doi(source.get('doi',''))
    if doi:return 'doi:'+doi
    document_hash=source.get('document_hash')
    if isinstance(document_hash,str) and re.fullmatch(r'[a-f0-9]{64}',document_hash):return 'document:'+document_hash
    title=source.get('title','').strip().casefold()
    if re.search(r'\.(?:pdf|txt)$',title) or not title:
        return 'document:'+_digest(source.get('text',''))
    identity=json.dumps([title,source.get('authors',[]),source.get('year')],ensure_ascii=False,sort_keys=True)
    return 'work:'+_digest(identity)


def deduplicate_sources(sources: list[dict]) -> list[dict]:
    """Collapse identical copies; preserve differing text and bibliographic works."""
    result, copies = [], {}
    for item in _sources(sources):
        doi = _doi(item.get('doi', ''))
        content_hash = _digest(item['text'])
        identity = json.dumps([item.get('title', '').strip().casefold(), item.get('authors', []),
                               item.get('year')], ensure_ascii=False, sort_keys=True)
        work_id = work_identity(item)
        key = (work_id, content_hash, item['scope'])
        origin = item.get('origin', 'user')
        if key in copies:
            saved = copies[key]
            saved['aliases'].append(item['id'])
            if origin not in saved['origins']:
                saved['origins'].append(origin)
            continue
        item.update(work_id=work_id, content_hash=content_hash, aliases=[], origins=[origin])
        copies[key] = item
        result.append(item)
    return result


def plan_literature(request: dict) -> dict:
    """Choose the next dialog action, never claim that a reading plan is evidence."""
    if not isinstance(request, dict):
        raise ValueError('literature request must be an object')
    for key in ('literature_prompted', 'network_allowed', 'search_exhausted'):
        if key in request and not isinstance(request[key], bool):
            raise ValueError(f'{key} must be boolean')
    anchor = _anchor(request.get('anchor'))
    provided = _sources(request.get('sources', []))
    unique = deduplicate_sources(provided)
    mode = 'none' if not unique else 'single' if len(unique) == 1 else 'multiple'
    result = dict(anchor=anchor, mode=mode, provided_count=len(provided),
                  source_ids=[s['id'] for s in unique], can_generate=False,
                  conflicts=deepcopy(request.get('critical_conflicts', [])))
    if result['conflicts']:
        return dict(result, action='clarify_conflict')
    if unique:
        action = 'read_and_synthesize' if any(s['text'].strip() for s in unique) else 'retrieve_sources'
        if action == 'retrieve_sources' and not request.get('network_allowed', True):
            action = 'explain_available_scope'
        return dict(result, action=action, reading_status='not_analyzed')
    if not request.get('literature_prompted', False):
        return dict(result, action='ask_for_literature')
    if not request.get('network_allowed', True):
        return dict(result, action='explain_available_scope')
    candidates = _sources(request.get('candidates', []))
    confirmed_id = request.get('confirmed_candidate_id')
    if confirmed_id is not None:
        selected = next((c for c in candidates if c['id'] == confirmed_id), None)
        if selected is None:
            raise ValueError('confirmed candidate was not offered')
        action = 'read_and_synthesize' if selected['text'].strip() else 'retrieve_sources'
        return dict(result, action=action, source_ids=[confirmed_id], reading_status='not_analyzed')
    if candidates:
        return dict(result, action='confirm_concept', candidate_ids=[c['id'] for c in candidates[:3]])
    if request.get('search_exhausted', False):
        return dict(result, action='request_source_hint')
    return dict(result, action='search', queries=build_search_queries(anchor))


def build_search_queries(anchor: dict, policy: LiteraturePolicy = DEFAULT_POLICY) -> list[str]:
    value = _anchor(anchor)
    doi = _doi(value.get('doi', ''))
    names = [doi] if doi else [value.get('english', '').strip(), value.get('term', '').strip()]
    if not any(names):
        names = [value['definition'].strip()[:240]]
    suffix = ' '.join(str(value[k]).strip() for k in ('author', 'year') if value.get(k))
    context=value.get('search_context','')
    if not doi and isinstance(context,str) and context.strip():
        # Prefer an explicit source clue when the user supplies one; otherwise
        # retain their recent clarification as retrieval context only.
        ids=re.findall(r'(?:arXiv[:\s/]+)(\d{4}\.\d{4,5}(?:v\d+)?)|(?:https?://arxiv\.org/(?:abs|html|pdf)/)(\d{4}\.\d{4,5}(?:v\d+)?)',context,re.I)
        if ids:return ['arxiv '+next(x for x in ids[-1] if x)]
        suffix=' '.join((suffix,context.rsplit('用户补充：',1)[-1].strip()[:90])).strip()
    queries = []
    for name in names:
        if name:
            # Query length is a provider constraint; retain the complete anchor.
            query = ' '.join(part for part in (name, suffix) if part)[:128]
            if query not in queries:
                queries.append(query)
    return queries[:policy.max_search_queries]


def select_reference_reads(references: list[dict], read_ids: set[str],
                           policy: LiteraturePolicy = DEFAULT_POLICY) -> list[dict]:
    """Choose purpose-assessed references, not every name in a bibliography."""
    if policy.max_reference_reads == 0 or policy.max_reference_depth == 0:
        return []
    candidates = []
    for item in references:
        if not isinstance(item, dict):
            raise ValueError('reference candidate must be an object')
        depth, priority = item.get('depth'), item.get('priority', 0)
        if not isinstance(depth, int) or isinstance(depth, bool) or depth < 1 or depth > policy.max_reference_depth:
            continue
        if not isinstance(priority, (int, float)) or isinstance(priority, bool) or not math.isfinite(priority):
            raise ValueError('reference priority must be finite')
        if not isinstance(item.get('purpose'), str) or not item['purpose'].strip():
            continue
        if item.get('module') not in MODULES or item.get('id') in read_ids:
            continue
        _text(item.get('id'), 'reference.id', required=True)
        _text(item.get('parent_id'), 'reference.parent_id', required=True)
        candidates.append(deepcopy(item))
    chosen, seen = [], set(read_ids)
    for item in sorted(candidates, key=lambda c: c.get('priority', 0), reverse=True):
        if item['id'] not in seen:
            chosen.append(item)
            seen.add(item['id'])
        if len(chosen) >= policy.max_reference_reads:
            break
    return chosen


def _located(reference, indexed, *, allow_locator=False):
    if not isinstance(reference, dict):
        raise ValueError('evidence reference must be an object')
    source = indexed.get(reference.get('source_id'))
    if source is None or source['scope'] == 'metadata':
        raise ValueError('evidence requires a known source with actual readable text')
    start, end = reference.get('start'), reference.get('end')
    if (not isinstance(start, int) or isinstance(start, bool)
            or not isinstance(end, int) or isinstance(end, bool)
            or not 0 <= start < end <= len(source['text'])
            or not source['text'][start:end].strip()):
        raise ValueError('evidence location is outside actual text')
    from .evidence import locator_overlap
    if not allow_locator and locator_overlap(source,start,end):raise ValueError('bibliography locator is not factual evidence')
    return dict(source_id=source['id'], start=start, end=end,
                excerpt=source['text'][start:end], scope=source['scope'])


def validate_source_relations(sources: list[dict], relations: list[dict]) -> list[dict]:
    indexed = {s['id']: s for s in _sources(sources)}
    if not isinstance(relations, list):
        raise ValueError('source relations must be an array')
    result = []
    for edge in relations:
        if not isinstance(edge, dict):
            raise ValueError('source relation must be an object')
        item = deepcopy(edge)
        source_id, target_id = item.get('source'), item.get('target')
        _text(source_id, 'relation.source', required=True)
        _text(target_id, 'relation.target', required=True)
        if source_id not in indexed or target_id not in indexed or source_id == target_id:
            raise ValueError('source relation must join distinct known documents')
        if not isinstance(item.get('type'), str) or item.get('type') not in RELATIONS:
            raise ValueError('unknown source relation type')
        _text(item.get('reason'), 'relation.reason', required=True)
        evidence = item.get('evidence', [])
        if not isinstance(evidence, list):
            raise ValueError('relation evidence must be an array')
        if item['type'] == 'cites':
            listed = indexed[source_id].get('references', [])
            listed_ids = {r.get('id') if isinstance(r, dict) else r for r in listed}
            if target_id not in listed_ids:
                raise ValueError('citation must actually occur in the reference list')
            located = [_located(ref, indexed,allow_locator=True) for ref in evidence]
            status = 'citation_list'
        else:
            if any(indexed[sid]['scope'] == 'metadata' for sid in (source_id, target_id)):
                raise ValueError('content relations require actual readable text for both documents')
            if not evidence:
                raise ValueError('content relation needs actual reading evidence')
            located = [_located(ref, indexed) for ref in evidence]
            if any(ref['source_id'] not in {source_id, target_id} for ref in located):
                raise ValueError('relation evidence must belong to one of its documents')
            status = 'located'
        item.update(evidence=located, evidence_status=status,
                    target_scope=indexed[target_id]['scope'], content_verified=False)
        result.append(item)
    return result


def build_evidence_matrix(sources: list[dict], claims: list[dict]) -> list[dict]:
    records = _sources(sources)
    indexed = {s['id']: s for s in records}
    works = {}
    for item in deduplicate_sources(records):
        for source_id in [item['id'], *item['aliases']]:
            works[source_id] = item['work_id']
    rows, seen = [], set()
    for claim in claims:
        item = deepcopy(claim)
        claim_id = _text(item.get('id'), 'claim.id', required=True)
        if claim_id in seen:
            raise ValueError('duplicate claim id')
        seen.add(claim_id)
        _text(item.get('statement'), 'claim.statement', required=True)
        if item.get('module') not in MODULES:
            raise ValueError('unknown evidence module')
        if item.get('stance') not in {'supports', 'disputes', 'qualifies'}:
            raise ValueError('unknown claim stance')
        if item.get('detail') not in {'overview', 'technical'}:
            raise ValueError('unknown claim detail level')
        references = item.get('evidence', [])
        if not isinstance(references, list) or not references:
            raise ValueError('claim requires evidence positions')
        located = [_located(ref, indexed) for ref in references]
        body_evidence = any(indexed[ref['source_id']].get('technical_evidence_eligible', ref['scope'] in {'excerpt','full_text'})
                            and ref['scope'] != 'abstract' for ref in located)
        item.update(evidence=located,
                    independent_work_count=len({works[r['source_id']] for r in located}),
                    evidence_status='needs_full_text' if item['detail'] == 'technical' and not body_evidence else 'located',
                    content_verified=False)
        rows.append(item)
    return rows


def assemble_evidence_bundle(anchor: dict, sources: list[dict], claims: list[dict],
                             relations: list[dict], *, critical_conflicts: list[str] | None = None,
                             required_modules=('definition', 'application')) -> dict:
    """Gate generation on prepared evidence, preserving unresolved research differences.

    This validates traceability and workflow readiness. Semantic correctness still
    needs review; distinct works do not establish independent study samples.
    """
    original = _anchor(anchor)
    if not isinstance(required_modules, (list, tuple)) or not required_modules:
        raise ValueError('required evidence modules must be specified')
    required = set(required_modules)
    if 'definition' not in required or not required <= MODULES:
        raise ValueError('a definition is always required for an explanation')
    if critical_conflicts is not None and not isinstance(critical_conflicts, list):
        raise ValueError('critical conflicts must be an array')
    questions = [_text(question, 'critical conflict', required=True)
                 for question in critical_conflicts or []]
    documents = _sources(sources)
    matrix = build_evidence_matrix(documents, claims)
    network = validate_source_relations(documents, relations)
    unresolved = [row['id'] for row in matrix if row['evidence_status'] != 'located']
    covered = {row['module'] for row in matrix
               if row['evidence_status'] == 'located' and row['stance'] != 'disputes'}
    differences = []
    grouped = {}
    for row in matrix:
        key = (row['module'], row['statement'].strip())
        grouped.setdefault(key, []).append(row)
    for (module, statement), group in grouped.items():
        stances = {row['stance'] for row in group}
        if {'supports', 'disputes'} <= stances:
            difference = dict(module=module, statement=statement,
                              claim_ids=[row['id'] for row in group])
            if module == 'definition':
                questions.append('定义证据存在相反陈述，请确认所指含义：' + statement)
            else:
                differences.append(difference)
    missing = sorted(required - covered)
    if questions:
        status = 'needs_disambiguation'
    elif missing or unresolved:
        status = 'needs_sources'
    else:
        status = 'ready_for_explanation'
    return dict(anchor=original, sources=documents, works=deduplicate_sources(documents),
                claims=matrix, source_relations=network, missing_modules=missing,
                unresolved_claims=unresolved, questions=questions,
                research_differences=differences, status=status,
                can_generate=status == 'ready_for_explanation', requires_semantic_review=True)
