"""Evidence retrieval for authoring term pages; baseline indexes remain read-only.

Search short child passages; reuse existing dense page signals and rerank with
child BM25. Parent context is separate and has an explicit character budget.
Mathematical expressions are supplied through reviewed external citations.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import pickle
import re
import functools
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_INDEX = HERE / 'rag_data' / 'editorial_candidate.pkl'
SOURCES = HERE / 'editorial_sources.json'
QUALITY_RULES = HERE / 'editorial_quality_rules.json'
CONCEPT_SOURCES = HERE / 'editorial_concepts.json'
QUALITY_NOTES = HERE / 'editorial_quality_notes.json'
TEXT_FIELDS = {'definition', 'operational_definition', 'plain_explanation', 'assumptions',
               'pitfalls', 'application', 'discovery'}
EXTERNAL_FIELDS = {'formula', 'diagram'}


def route_field(field):
    if field in EXTERNAL_FIELDS:
        return {'channel': 'external_verified', 'allow_ocr_formula': False,
                'require': ['authority_url', 'conditions', 'variables', 'review_status']}
    if field in TEXT_FIELDS:
        return {'channel': 'textbook_rag', 'allow_ocr_formula': False}
    raise ValueError('unknown field: ' + field)


def term_catalog():
    catalog = {}
    for path in [HERE / 'editorial_terms.json', ROOT / 'site/content/terms_draft.json',
                 ROOT / 'site/content/registry.json']:
        if path.is_file():
            for entry in json.loads(path.read_text(encoding='utf-8'))['terms']:
                slug = entry.get('slug') or entry.get('id')
                if slug:
                    catalog.setdefault(slug, dict(entry, slug=slug))
    return catalog


def resolve_term(term):
    if isinstance(term, dict):
        return term
    for entry in term_catalog().values():
        if normalized(term) in {normalized(entry.get(k, '')) for k in ['slug', 'zh', 'en']}:
            return {k: entry.get(k, [] if k == 'aliases' else '') for k in ['slug', 'zh', 'en', 'aliases']}
    return {'slug': term, 'zh': term, 'en': '', 'aliases': []}


def normalized(text):
    return re.sub(r'\s+', '', text).lower()


def clean_text(text):
    text = text.replace('\x00', '').replace('\u00ad', '')
    lines = []
    for line in text.splitlines():
        line = re.sub(r'[ \t]+', ' ', line).strip()
        # Character-spaced Chinese is layout, not a word boundary.
        for _ in range(2):
            line = re.sub(r'([\u4e00-\u9fff]) +(?=[\u4e00-\u9fff，。；、：])', r'\1', line)
        if line:
            lines.append(line)
    return '\n'.join(lines)


def content_status(text):
    key = normalized(text)
    if re.search(r'p接受h[0o].{0,8}拒绝h[1i].{0,8}否则接受h[1i]', key):
        return {'status': 'quarantined', 'reason': 'hypothesis_decision_condition_lost'}
    if re.search(r'虚无假设为真.{0,12}假定是正确', key):
        return {'status': 'quarantined', 'reason': 'non_rejection_claims_truth'}
    letters = len(re.findall(r'[A-Za-z\u4e00-\u9fff]', text))
    if letters < 12:
        return {'status': 'non_prose', 'reason': 'insufficient_explanatory_text'}
    if sum(text.upper().count(x) for x in ['VARIABLE:', 'USEV ', 'OUTPUT:', 'SAVEDATA:', 'DATA:FILE']) >= 2:
        return {'status': 'software_syntax', 'reason': 'code_requires_software_specific_task'}
    return {'status': 'usable', 'reason': 'prose_candidate_pending_claim_review'}


@functools.lru_cache(maxsize=4)
def _read_quality_rules(stamp):
    return json.loads(QUALITY_RULES.read_text(encoding='utf-8'))['rules'] if stamp else []


def reviewed_status(item, pages=None, rules=None):
    """Apply reviewed spans before and after chunking, including boundary overlaps."""
    status = content_status(item['text'])
    if status['status'] != 'usable':
        return status
    if rules is None:
        rules = _read_quality_rules(QUALITY_RULES.stat().st_mtime_ns if QUALITY_RULES.exists() else 0)
    page_no = item.get('page_course') or item.get('page_pdf')
    doc = item.get('doc') or ('advanced' if item['source'] == 'textbook' else 'basic')
    relevant = [r for r in rules if (r['source'], r['doc'], r['page_pdf']) == (item['source'], doc, page_no)]
    if not relevant:
        return status
    child = normalized(item['text'])
    parent = pages.get(item.get('parent_id')) if pages else None
    if parent is None and pages:
        matching = [p for p in pages.values() if p['source'] == item['source'] and p['doc'] == doc and
                    p['page_pdf'] == page_no and child in normalized(p['text'])]
        parent = next((p for p in matching if all(normalized(r['match_text']) in normalized(p['text']) for r in relevant)), None)
    body = normalized(parent['text']) if parent else child
    start = body.find(child)
    for rule in relevant:
        needle = normalized(rule['match_text'])
        if needle in child:
            return {'status': 'quarantined', 'reason': 'independent_knowledge_review', 'finding_id': rule['id']}
        bad_start = body.find(needle)
        if parent and start >= 0 and bad_start >= 0:
            if start < bad_start + len(needle) and start + len(child) > bad_start:
                return {'status': 'quarantined', 'reason': 'reviewed_span_crosses_child_boundary', 'finding_id': rule['id']}
        elif not parent or bad_start < 0:
            # Different extraction variants cannot safely map the reviewed span.
            return {'status': 'quarantined', 'reason': 'reviewed_page_unmapped_variant', 'finding_id': rule['id']}
    return status


def safe_anchors(rows, pages):
    safe, audit = [], []
    for row in rows:
        status = reviewed_status(row, pages)
        if status['status'] == 'usable':
            safe.append(row)
        else:
            audit.append({k: row.get(k) for k in ['source', 'doc', 'page_pdf', 'page_course', 'chunk_id']})
            audit[-1]['quality'] = status
    return safe, audit


def primary_ranking(anchors, supplements, k=8):
    primary = [dict(row, rank=i) for i, row in enumerate(anchors[:k], 1)]
    seen = {normalized(r['text']) for r in primary}
    for row in supplements:
        if len(primary) >= k:
            break
        if normalized(row['text']) not in seen:
            primary.append(dict(row, rank=len(primary) + 1))
            seen.add(normalized(row['text']))
    return primary


def concept_supplement(term):
    if not CONCEPT_SOURCES.exists():
        return None
    data = json.loads(CONCEPT_SOURCES.read_text(encoding='utf-8'))
    records = data.get('records', []) if isinstance(data, dict) else data
    return next((r for r in records if r['slug'] == term['slug'] and
                 (r.get('decision') == 'pass' or r.get('review_status', r.get('reviewstatus')) in {'pass', 'approved'}) and
                 r.get('authority_urls')), None)


def chunk_page(page, target=420, maxlen=700, overlap=80):
    if target < 1 or maxlen < target or overlap < 0 or overlap >= target:
        raise ValueError('require 0 <= overlap < target <= maxlen')
    text = clean_text(page['text'])
    units = re.findall(r'[^。！？；\n]+[。！？；]?|\n', text)
    units = [u for u in units if u.strip()]
    bounded = [u[i:i + maxlen] for u in units for i in range(0, len(u), maxlen)]
    pieces, current = [], ''
    for unit in bounded:
        if current and len(current) + len(unit) + 1 > maxlen:
            pieces.append(current); current = ''
        current += ('\n' if current else '') + unit
        if len(current) >= target:
            pieces.append(current); current = ''
    if current:
        pieces.append(current)
    result = []
    for i, piece in enumerate(pieces):
        if i and overlap:
            previous = pieces[i - 1].splitlines()[-1]
            if len(previous) <= overlap and len(previous) + len(piece) + 1 <= maxlen:
                piece = previous + '\n' + piece
        item = {k: v for k, v in page.items() if k != 'text'}
        item.update(id=page['id'] + ':child:' + str(i), parent_id=page['id'], text=piece,
                    child_no=i, quality=content_status(piece))
        result.append(item)
    return result


def expand_context(rows, pages, budget=9000):
    if budget < 0:
        raise ValueError('budget must be nonnegative')
    out, seen, left = [], set(), budget
    for row in rows:
        pid = row['parent_id']
        if pid in seen or left <= 0:
            continue
        seen.add(pid)
        page = pages[pid]
        if page['doc'] != row['doc'] or page['source'] != row['source']:
            raise ValueError('parent provenance mismatch')
        text = page['text']
        # An unsafe parent cannot reintroduce a quarantined paragraph.
        if reviewed_status(page, pages)['status'] == 'quarantined':
            text = row['text']
        checked = dict(row, text=text)
        if reviewed_status(checked, pages)['status'] != 'usable':
            continue
        if len(text) > left:
            needle = row['text'][:60]
            pos = max(0, text.find(needle))
            start = max(0, pos - min(200, left // 4))
            text = text[start:start + left]
        if reviewed_status(dict(page, text=text), pages)['status'] != 'usable':
            continue
        entry = {k: v for k, v in page.items() if k != 'text'}
        entry.update(text=text, context_characters=len(text), truncated=len(text) < len(page['text']),
                     ocr_formula_usable=False)
        out.append(entry); left -= len(text)
    return out


def evidence_context(anchors, rows, pages, budget=9000):
    """Keep coarse evidence intact before adding native/parent complements."""
    result, seen, remaining = [], set(), budget
    for row in anchors:
        if remaining <= 0:
            break
        if reviewed_status(row, pages)['status'] != 'usable':
            continue
        text = row['text'][:remaining]
        if len(text) < len(row['text']) and reviewed_status(dict(row, text=text), pages)['status'] != 'usable':
            continue
        key = normalized(text)
        if key in seen:
            continue
        entry = dict(row, text=text, context_role='coarse_anchor', ocr_formula_usable=False,
                     truncated=len(text) < len(row['text']))
        result.append(entry); seen.add(key); remaining -= len(text)
    for entry in expand_context(rows, pages, remaining):
        key = normalized(entry['text'])
        if key not in seen:
            entry['context_role'] = 'native_or_parent_complement'
            result.append(entry); seen.add(key)
    return result


class EditorialRetriever:
    def __init__(self, index=DEFAULT_INDEX):
        from rag_core import BM25, tokenize
        with Path(index).open('rb') as handle:
            self.data = pickle.load(handle)
        self.pages = self.data['pages']
        self.chunks = self.data['chunks']
        self.emb = np.asarray(self.data['legacy_embeddings'], dtype=np.float32)
        self.emb /= np.clip(np.linalg.norm(self.emb, axis=1, keepdims=True), 1e-9, None)
        self.child_emb = np.asarray(self.data['child_embeddings'], dtype=np.float32) if 'child_embeddings' in self.data else None
        if self.child_emb is not None:
            self.child_emb /= np.clip(np.linalg.norm(self.child_emb, axis=1, keepdims=True), 1e-9, None)
        self.parent_legacy = self.data['parent_legacy']
        self.bm25 = BM25([tokenize(c['text']) for c in self.chunks])
        self.cache = {}

    def retrieve(self, term, *, field='definition', k=8, sources=('textbook', 'basic', 'course'),
                 context_budget=9000, query_vectors=None, include_anchors=True):
        route = route_field(field)
        if route['channel'] != 'textbook_rag':
            return external_evidence(term, field)
        if k < 1 or context_budget < 0:
            raise ValueError('invalid retrieval budget')
        if not set(sources) <= {'textbook', 'basic', 'course'}:
            raise ValueError('unknown source')
        from rag_core import embed_texts, tokenize
        term = resolve_term(term)
        aliases = [term.get('zh', ''), term.get('en', '')] + list(term.get('aliases', []))
        aliases = [a.strip() for a in aliases if a.strip()]
        query = ' '.join(aliases)
        facets = [query, query + ' 定义 含义 原理', query + ' 前提 条件 注意 区别']
        cache_key = tuple(facets)
        if query_vectors is None:
            if cache_key not in self.cache:
                self.cache[cache_key] = embed_texts(facets)
            vecs = self.cache[cache_key]
        else:
            vecs = query_vectors
        vecs = vecs / np.clip(np.linalg.norm(vecs, axis=1, keepdims=True), 1e-9, None)
        dense = np.max(self.emb @ vecs.T, axis=1)
        parent_dense = {pid: float(max(dense[i] for i in positions)) if positions else 0.
                        for pid, positions in self.parent_legacy.items()}
        child_dense = (self.child_emb @ vecs.T) if self.child_emb is not None else None
        child_score = (0.65 * child_dense[:, 0] + 0.35 * np.max(child_dense, axis=1)) if child_dense is not None else None
        lex = self.bm25.scores(tokenize(query))
        candidates = []
        # A single global pool avoids each source receiving an accidental fixed quota.
        for i, c in enumerate(self.chunks):
            if c['source'] not in sources or reviewed_status(c, self.pages)['status'] != 'usable':
                continue
            if field != 'discovery' and c.get('is_catalog'):
                continue
            candidates.append(i)
        dense_order = sorted(candidates, key=lambda i: (-(float(child_score[i]) if child_score is not None else parent_dense.get(self.chunks[i]['parent_id'], 0)), i))
        lex_order = sorted(candidates, key=lambda i: (-float(lex[i]), i))
        dr = {i: n for n, i in enumerate(dense_order, 1)}
        lr = {i: n for n, i in enumerate(lex_order, 1)}
        scores = {}
        for i in set(dense_order[:240]) | set(lex_order[:240]):
            c = self.chunks[i]
            exact = any(normalized(a) in normalized(c['text']) for a in aliases if len(normalized(a)) >= 2)
            prose = bool(re.search(r'定义|是指|指的是|称为|假设|条件|注意|不能|不等于|表示|defined|refers', c['text'], re.I))
            value = 1.3 / (60 + dr[i]) + 1 / (60 + lr[i])
            value *= 1.35 if exact else 1.
            value *= 1.08 if prose else 1.
            if re.search(r'核心要点|关键术语|学习目标|本章内容|本章节内容', c['text'][:150]):
                value *= 0.45
            if c['text'].count('|') >= 8:
                value *= 0.55
            scores[i] = value
        ranked = sorted(scores, key=lambda i: (-scores[i], self.chunks[i]['id']))
        rows, parent_count, seen_text = [], collections.Counter(), set()
        for i in ranked:
            c = self.chunks[i]
            text_key = normalized(c['text'])
            if text_key in seen_text or parent_count[c['parent_id']] >= 2:
                continue
            row = dict(c, rank=len(rows) + 1, score=round(scores[i], 7),
                       dense_parent_similarity=round(parent_dense.get(c['parent_id'], 0), 5),
                       child_similarity=round(float(child_score[i]), 5) if child_score is not None else None,
                       lexical_rank=lr[i], formula_usable=False)
            rows.append(row); seen_text.add(text_key); parent_count[c['parent_id']] += 1
            if len(rows) == k:
                break
        if include_anchors:
            from rag_multi import retrieve_multi
            anchors = retrieve_multi(query, k=k, sources=sources)
        else:
            anchors = []
        for anchor in anchors:
            anchor['doc'] = anchor.get('doc') or ('advanced' if anchor['source'] == 'textbook' else 'basic')
            anchor['method'] = 'legacy_index'
            anchor['id'] = 'legacy:' + anchor['source'] + ':' + str(anchor['chunk_id'])
        anchors, anchor_audit = safe_anchors(anchors, self.pages)
        fine_rows = rows
        primary = primary_ranking(anchors, fine_rows, k)
        contexts = evidence_context(anchors, rows, self.pages, context_budget)
        notes = []
        rules = _read_quality_rules(QUALITY_RULES.stat().st_mtime_ns if QUALITY_RULES.exists() else 0)
        candidate_pages = {(r['source'], r['doc'], r.get('page_course') or r.get('page_pdf')) for r in rows + anchors}
        conditional_notes = (json.loads(QUALITY_NOTES.read_text(encoding='utf-8'))['notes']
                             if QUALITY_NOTES.exists() else [])
        for rule in rules + conditional_notes:
            if (rule['source'], rule['doc'], rule['page_pdf']) in candidate_pages:
                notes.append({'finding_id': rule['id'], 'channel': 'external_scientific_review',
                              'severity': rule.get('severity', 'major'),
                              'correction_note': rule['reason'], 'instruction': rule['suggestion'],
                              'authority_urls': rule['authority_urls']})
        return {'channel': route['channel'], 'term': term, 'field': field, 'queries': facets,
                'rows': primary, 'supplemental_rows': fine_rows, 'anchor_rows': anchors,
                'anchor_audit': anchor_audit, 'contexts': contexts,
                'retrieval_strategy': 'legacy_hybrid_primary_with_fine_context_complements',
                'retrieved_characters': sum(len(r['text']) for r in primary),
                'context_characters': sum(len(r['text']) for r in contexts),
                'context_budget': context_budget, 'formula_policy': 'external_verified_only',
                'external_review_notes': notes,
                'external_concept_evidence': concept_supplement(term),
                'generation_instruction': '只将文字证据用于定义、条件和解释；引用页码。公式与图示须另取外部证据。遇到教材冲突保留缺口，不以常识补写来源。'}


def external_evidence(term, field='formula', registry=SOURCES):
    if field not in EXTERNAL_FIELDS:
        raise ValueError('external_evidence requires formula or diagram')
    term = resolve_term(term)
    data = json.loads(Path(registry).read_text(encoding='utf-8')) if Path(registry).exists() else {'records': []}
    item = next((r for r in data['records'] if r['slug'] == term['slug']), None)
    # A needs-revision formula never becomes a deliverable merely because a URL exists.
    approved = item and item.get('decision') == 'pass' and item.get('authority_urls') and item.get('conditions') and item.get('variables')
    return {'channel': 'external_verified', 'field': field, 'term': term,
            'status': ('evidence_available_needs_diagram_review' if field == 'diagram' else 'available') if approved else 'needs_source_review',
            'evidence': item if approved else None,
            'generation_instruction': ('按来源条件引用公式并解释符号；图示须依据关系自行绘制且标明示意图。'
                                       if approved else '证据尚未核定，保留缺口并查权威原文。'),
            'allow_ocr_formula': False}


def model_payload(result):
    if result.get('channel') != 'textbook_rag':
        return result
    keys = ['channel', 'term', 'field', 'contexts', 'context_characters', 'context_budget',
            'formula_policy', 'external_review_notes', 'external_concept_evidence', 'generation_instruction']
    return {k: result[k] for k in keys if k in result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('term')
    parser.add_argument('--en', default='')
    parser.add_argument('--field', default='definition', choices=sorted(TEXT_FIELDS | EXTERNAL_FIELDS))
    parser.add_argument('--index', type=Path, default=DEFAULT_INDEX)
    parser.add_argument('--k', type=int, default=8)
    parser.add_argument('--budget', type=int, default=9000)
    parser.add_argument('--package', action='store_true', help='return separately attributed text and formula evidence')
    parser.add_argument('--diagnostics', action='store_true', help='also return safe child and anchor ranking details')
    args = parser.parse_args()
    term = resolve_term(args.term)
    if args.en:
        term['en'] = args.en
    result = (external_evidence(term, args.field) if args.field in EXTERNAL_FIELDS else
              EditorialRetriever(args.index).retrieve(term, field=args.field, k=args.k, context_budget=args.budget))
    if not args.diagnostics:
        result = model_payload(result)
    if args.package:
        result = {'text_evidence': result, 'formula_evidence': external_evidence(term),
                  'source_allocation': {'textbook_rag': 'definition, operation, explanation, assumptions, pitfalls',
                                        'external_verified': 'formula, notation, mathematical conditions, diagram relationships'},
                  'publication_instruction': '按条引用来源；图示仍需生成后检查。不要把检索证据自动认定为完整术语页。'}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
