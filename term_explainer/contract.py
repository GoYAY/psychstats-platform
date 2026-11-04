"""Version-one teaching boundary; raw model output never goes straight to HTML."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import json
import re

from .evidence import resolve_reference
from .literature import SCOPES, _sources, _doi


REQUIRED_BLOCKS = frozenset({'real_question', 'operational_definition', 'plain_explanation',
                            'detailed_explanation', 'how_to_use'})
RELATION_TYPES = frozenset({'prerequisites', 'components', 'contrasts', 'used_in', 'next'})
UNSAFE_MATH = re.compile(r'\\(?:href|url|html\w*|includegraphics|input|write|def|gdef|newcommand|renewcommand)\b')
ANALYSIS_CODE = re.compile(r'```|(?:install\.packages|library|require)\s*\(|\b(?:lm|glm|lavaan|read\.csv)\s*\(')
SAFE_ID = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,95}')


def used_source_ids(value):
    if hasattr(value,'blocks'):
        from dataclasses import asdict
        value=asdict(value)
    if isinstance(value,dict):
        return {r['source_id'] for r in value.get('refs',[]) if 'source_id' in r} | set().union(*(used_source_ids(v) for k,v in value.items() if k not in {'provenance','source_relations','refs'}))
    if isinstance(value,list):return set().union(*(used_source_ids(v) for v in value))
    return set()


@dataclass
class LessonRequest:
    request_id: str
    term: dict
    question: str
    sources: list[dict]
    catalog: list[dict]
    known_terms: list[dict]
    literature_prompted: bool = False
    network_allowed: bool = True
    max_body_chars: int | None = None
    optional_reference_reads: bool = False
    max_reference_reads: int = 3
    allow_limited_delivery: bool = False


@dataclass
class LessonResult:
    schema_version: int
    content_id: str
    status: str
    term: dict
    blocks: list[dict]
    formulas: list[dict]
    visual: dict | None
    quiz: dict | None
    relations: list[dict]
    missing_evidence: list[str]
    provenance: dict
    source_relations: list[dict] = field(default_factory=list)
    limitations: list[dict] = field(default_factory=list)
    glossary: list[dict] = field(default_factory=list)


def _string(value, name, *, empty=False, maximum=12000):
    if not isinstance(value, str) or (not empty and not value.strip()) or len(value) > maximum:
        raise ValueError(f'invalid {name}')
    return value


def _identifier(value, name):
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
        raise ValueError(f'invalid {name}')
    return value


def _array(value, name, maximum=100):
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError(f'invalid {name}')
    return value


def _object(value, name):
    if not isinstance(value, dict):
        raise ValueError(f'{name} must be an object')
    return value


def validate_request(value: dict) -> LessonRequest:
    if not isinstance(value, dict):
        raise ValueError('request must be an object')
    if len(json.dumps(value, ensure_ascii=False).encode()) > 1048576:
        raise ValueError('request exceeds 1 MiB')
    request_id = _identifier(value.get('request_id'), 'request_id')
    term = deepcopy(value.get('term'))
    if not isinstance(term, dict):
        raise ValueError('term must be an object')
    _identifier(term.get('id'), 'term.id')
    for key in ('zh', 'en', 'definition'):
        term[key] = _string(term.get(key, ''), f'term.{key}', empty=True)
    if not (term['zh'].strip() or term['definition'].strip()):
        raise ValueError('provide a term or definition')
    for key in ('author', 'doi'):
        if key in term:
            _string(term[key], f'term.{key}', empty=True, maximum=500)
    if 'doi' in term:
        _doi(term['doi'])
    if 'year' in term and (type(term['year']) is not int or not 1000 <= term['year'] <= 9999):
        raise ValueError('term.year must be a four-digit year')
    term.setdefault('aliases', [])
    for alias in _array(term['aliases'], 'aliases', 20):
        _string(alias, 'alias', maximum=100)
    sources = _sources(_array(value.get('sources', []), 'sources', 10))
    if any(len(s['text']) > 60000 for s in sources) or sum(len(s['text']) for s in sources) > 120000:
        raise ValueError('source text exceeds selected-source limits')
    catalogs = []
    for name in ('catalog', 'known_terms'):
        entries = deepcopy(_array(value.get(name, []), name, 2000))
        seen = set()
        for item in entries:
            if not isinstance(item, dict):
                raise ValueError('invalid term reference')
            _identifier(item.get('id'), 'catalog.id')
            if item['id'] in seen or item.get('kind') not in {'classic', 'personal', 'pending'}:
                raise ValueError('ambiguous or invalid catalog entry')
            seen.add(item['id'])
            _string(item.get('zh', ''), 'catalog.zh', empty=True)
            for alias in _array(item.get('aliases', []), 'catalog.aliases', 20):
                _string(alias, 'catalog.alias', maximum=100)
        catalogs.append(entries)
    for key in ('literature_prompted', 'network_allowed','optional_reference_reads','allow_limited_delivery'):
        if key in value and type(value[key]) is not bool:
            raise ValueError(f'{key} must be boolean')
    body_limit=value.get('max_body_chars')
    if body_limit is not None and (type(body_limit) is not int or not 1<=body_limit<=12000):
        raise ValueError('max_body_chars must be an integer between 1 and 12000')
    reference_limit=value.get('max_reference_reads',3)
    if type(reference_limit) is not int or not 0<=reference_limit<=3:raise ValueError('max_reference_reads must be between 0 and 3')
    return LessonRequest(request_id, term, _string(value.get('question', ''), 'question', empty=True),
                         sources, *catalogs, value.get('literature_prompted', False),
                         value.get('network_allowed', True),body_limit,value.get('optional_reference_reads',False),reference_limit,
                         value.get('allow_limited_delivery',False))


def validate_result(value: dict, request: LessonRequest) -> LessonResult:
    if not isinstance(value, dict):
        raise ValueError('lesson must be an object')
    allowed = set(LessonResult.__dataclass_fields__)
    if set(value) - allowed:
        raise ValueError('unknown lesson fields are not executable extensions')
    data = deepcopy(value)
    if type(data.get('schema_version')) is not int or data['schema_version'] != 1:
        raise ValueError('unsupported schema version')
    if not isinstance(data.get('status'), str) or data.get('status') not in {'complete', 'needs_sources', 'needs_disambiguation'}:
        raise ValueError('invalid teaching status')
    term = data.get('term')
    if not isinstance(term, dict) or any(term.get(key, '') != request.term.get(key, '')
                                        for key in ('id', 'zh', 'en', 'definition')):
        raise ValueError('the model cannot replace the user term or definition')
    data['content_id'] = 'lesson-' + request.request_id
    data['term'] = deepcopy(request.term)
    data.setdefault('provenance', {})
    data.setdefault('source_relations', [])
    data.setdefault('limitations', [])
    data.setdefault('glossary', [])
    for key in ('blocks', 'formulas', 'relations', 'missing_evidence'):
        data.setdefault(key, [])
    for key in ('visual', 'quiz'):
        data.setdefault(key, None)
    if not isinstance(data['provenance'], dict):
        raise ValueError('invalid provenance')
    missing = _array(data.get('missing_evidence', []), 'missing_evidence', 30)
    for item in missing:
        _string(item, 'missing evidence')
    if data['status'] != 'complete' and not missing:
        raise ValueError('partial output must explain its missing information')

    def refs(values):
        return [resolve_reference(ref, request.sources) for ref in _array(values, 'refs', 30)]

    for note in _array(data['limitations'],'limitations',20):
        _object(note,'limitation')
        _string(note.get('text'),'limitation.text',maximum=2000)
        note['refs']=refs(note.get('refs',[]))
        if not note['refs']: raise ValueError('research limits require source evidence')

    glossary_ids=set(); glossary_names=set()
    known_targets={t['id'] for t in request.catalog+request.known_terms}
    for item in _array(data['glossary'],'glossary',40):
        _object(item,'glossary item')
        if set(item)-{'id','term','aliases','explanation','refs','target'}: raise ValueError('unknown glossary fields')
        key=_identifier(item.get('id'),'glossary.id')
        if key in glossary_ids: raise ValueError('duplicate glossary id')
        glossary_ids.add(key)
        name=_string(item.get('term'),'glossary.term',maximum=120)
        _string(item.get('explanation'),'glossary.explanation',maximum=240)
        item.setdefault('aliases',[])
        labels=[name]+[_string(a,'glossary.alias',maximum=120) for a in _array(item['aliases'],'glossary.aliases',8)]
        names={label.casefold() for label in labels}
        if names.intersection(glossary_names): raise ValueError('ambiguous glossary names')
        glossary_names.update(names)
        if item.get('target') is not None:
            target=_identifier(item['target'],'glossary.target')
            if target not in known_targets or target==request.term['id']: raise ValueError('unknown or self glossary target')
        item['refs']=refs(item.get('refs',[]))
        if not item['refs']: raise ValueError('glossary explanations require original evidence')

    seen_blocks = set()
    for block in _array(data.get('blocks', []), 'blocks', 10):
        if isinstance(block,dict) and isinstance(block.get('id'),str):
            alias=block['id'].replace('-','_')
            if alias in REQUIRED_BLOCKS|{'academic_expression'}:block['id']=alias
        if not isinstance(block, dict) or not isinstance(block.get('id'), str) or block.get('id') not in REQUIRED_BLOCKS | {'academic_expression'}:
            raise ValueError('invalid teaching block')
        if block['id'] in seen_blocks:
            raise ValueError('duplicate teaching block')
        seen_blocks.add(block['id'])
        _string(block.get('heading'), 'block.heading', maximum=100)
        paragraphs = _array(block.get('paragraphs'), 'paragraphs', 20)
        if not paragraphs:
            raise ValueError('block requires explanatory text')
        for paragraph in paragraphs:
            if not isinstance(paragraph, dict):
                raise ValueError('invalid paragraph')
            text = _string(paragraph.get('text'), 'paragraph.text')
            if ANALYSIS_CODE.search(text):
                raise ValueError('analysis code is outside the teaching scope')
            if not isinstance(paragraph.get('kind'), str) or paragraph.get('kind') not in {'factual', 'analogy', 'illustration'}:
                raise ValueError('unknown paragraph type')
            for emphasis in _array(paragraph.get('emphasis', []), 'emphasis', 20):
                if _string(emphasis, 'emphasis') not in text:
                    raise ValueError('emphasis must select existing text')
            paragraph['refs'] = refs(paragraph.get('refs', []))
            if paragraph['kind'] == 'factual' and not paragraph['refs']:
                raise ValueError('factual explanations require locatable source evidence')

    for formula in _array(data.get('formulas', []), 'formulas', 5):
        _object(formula, 'formula')
        latex = _string(formula.get('latex'), 'formula.latex', maximum=2000)
        if UNSAFE_MATH.search(latex):
            raise ValueError('untrusted math commands')
        if not formula.get('symbols'):
            raise ValueError('formula requires symbol explanations')
        for item in _array(formula.get('symbols', []), 'symbols', 30):
            _object(item, 'symbol')
            _string(item.get('symbol'), 'symbol', maximum=100)
            _string(item.get('meaning'), 'symbol meaning', maximum=500)
        formula['refs'] = refs(formula.get('refs', []))
        if not formula['refs']:
            raise ValueError('formula requires source evidence')

    visual = data.get('visual')
    if visual is not None:
        if not isinstance(visual, dict) or not isinstance(visual.get('kind'), str) or visual.get('kind') not in {'story', 'statistical'}:
            raise ValueError('invalid visual type')
        if not isinstance(visual.get('origin'), str) or visual.get('origin') not in {'conceptual', 'teaching', 'source', 'theoretical'}:
            raise ValueError('invalid visual provenance')
        for key in ('title', 'takeaway', 'alt'):
            _string(visual.get(key), f'visual.{key}', maximum=1000)
        if not isinstance(visual.get('payload'), dict) or not visual['payload']:
            raise ValueError('visual requires a meaningful specification')
        visual['refs'] = refs(visual.get('refs', []))
        if visual['origin'] in {'source', 'theoretical'} and not visual['refs']:
            raise ValueError('source or theory figure requires supporting evidence')
        from .figures import validate_visual
        validate_visual(visual)

    quiz = data.get('quiz')
    if quiz is not None:
        _object(quiz, 'quiz')
        _string(quiz.get('question'), 'quiz.question')
        options = _array(quiz.get('options'), 'quiz.options', 4)
        if len(options) != 4 or {_identifier(_object(o, 'option').get('id'), 'option.id') for o in options} != {'a', 'b', 'c', 'd'}:
            raise ValueError('quiz requires four distinct options')
        if not isinstance(quiz.get('correct_option'), str) or quiz.get('correct_option') not in {'a', 'b', 'c', 'd'}:
            raise ValueError('quiz answer must refer to an option')
        for option in options:
            _string(option.get('text'), 'option.text')
            _string(option.get('explanation'), 'option.explanation')

    known = {t['id']: t for t in request.catalog + request.known_terms}
    for relation in _array(data.get('relations', []), 'relations', 20):
        _object(relation, 'relation')
        _identifier(relation.get('target'), 'relation.target')
        if not isinstance(relation.get('type'), str) or relation.get('type') not in RELATION_TYPES or relation.get('target') not in known:
            raise ValueError('relation must target a known or explicitly pending term')
        if relation['target'] == request.term['id']:
            raise ValueError('self relation is not a teaching prerequisite')
        _string(relation.get('reason'), 'relation.reason')
        relation['refs'] = refs(relation.get('refs', []))
        if not relation['refs']:
            raise ValueError('teaching relation requires evidence')
    if _array(data['source_relations'], 'source_relations', 50):
        from .literature import validate_source_relations
        data['source_relations'] = validate_source_relations(request.sources, data['source_relations'])
    if data['status'] == 'complete':
        if not REQUIRED_BLOCKS <= seen_blocks or not visual or not quiz:
            raise ValueError('complete teaching output lacks required modules')
        if missing:
            raise ValueError('complete output cannot conceal material evidence gaps')
    if request.max_body_chars is not None:
        count=sum(len(p['text']) for b in data['blocks'] for p in b['paragraphs'])
        if count>request.max_body_chars:
            raise ValueError(f'body has {count} characters; maximum {request.max_body_chars}; shorten prose without removing modules')
    return LessonResult(**data)
