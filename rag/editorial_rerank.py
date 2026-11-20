"""Local term-page evidence retrieval with joint ranking and optional relation queries."""
import argparse
import collections
import json
import re
from pathlib import Path

import numpy as np

from editorial_rag import (DEFAULT_INDEX, ROOT, TEXT_FIELDS, EXTERNAL_FIELDS, QUALITY_NOTES, QUALITY_RULES,
                           EditorialRetriever, evidence_context, external_evidence,
                           model_payload, normalized, resolve_term, term_catalog)
from rag_multi import load_basic, load_course, load_textbook

DRAFTS = ROOT / 'site/content/drafts'
EDGE_ORDER = {
    'definition': ('used_in', 'components', 'prerequisites'),
    'operational_definition': ('used_in', 'components', 'prerequisites'),
    'plain_explanation': ('components', 'used_in', 'prerequisites'),
    'assumptions': ('prerequisites', 'used_in'),
    'pitfalls': ('contrasts', 'used_in'),
    'application': ('used_in', 'prerequisites'),
}
EVIDENCE_WORDS = re.compile(r'是指|指的是|定义|称为|用于|表示|假设|前提|条件|区别|\b(?:defined|refers|means|assumes)\b', re.I)
BIBLIOGRAPHY = re.compile(r'参考文献|\breferences\b|\bdoi\s*:', re.I)
CONTENTS = re.compile(r'学习目标|本章内容|本章节内容|^(?:目录|内容简介|关键术语)', re.M)


def related_query(slug, field, catalog, drafts=DRAFTS):
    if slug not in catalog or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug):
        return None
    file = Path(drafts) / (slug + '.json')
    if field not in EDGE_ORDER:
        return None
    term = json.loads(file.read_text(encoding='utf-8')) if file.is_file() else catalog[slug]
    relations = term.get('relations', {})
    for edge in EDGE_ORDER[field]:
        for neighbor in relations.get(edge, []):
            if neighbor == slug or neighbor not in catalog:
                continue
            entry = catalog[neighbor]
            names = [name.strip() for name in (entry.get('zh', ''), entry.get('en', '')) if name.strip()]
            if names:
                return {'type': edge, 'slug': neighbor, 'names': names}
    return None


def mentions(text, aliases):
    compact = normalized(text)
    for alias in aliases:
        name = normalized(alias)
        if re.search(r'[\u4e00-\u9fff]', name):
            if len(name) >= 2 and name in compact:
                return True
        elif len(name) >= 3 and re.search(r'(?<!\w)' + re.escape(alias) + r'(?!\w)', text, re.I):
            return True
    return False


def rank_evidence(candidates, similarities, aliases, k):
    """Use the same score for either index, irrespective of its original rank."""
    scored = []
    for row, similarity in zip(candidates, similarities, strict=True):
        body = row['text']
        score = float(similarity)
        if mentions(body, aliases):
            score += 0.08
            if any(EVIDENCE_WORDS.search(part) and mentions(part, aliases)
                   for part in re.split(r'[。！？；]', body)):
                score += 0.025
        if row.get('is_catalog') or CONTENTS.search(body[:180]):
            score -= 0.13
        if BIBLIOGRAPHY.search(body[:180]) or len(re.findall(r'\([12]\d{3}[a-z]?\)', body)) >= 3:
            score -= 0.16
        if body.count('|') >= 8 and not EVIDENCE_WORDS.search(body):
            score -= 0.13
        scored.append((score, row))
    scored.sort(key=lambda item: (-item[0], item[1]['id']))
    by_page = collections.defaultdict(list)
    output, seen = [], set()
    for score, row in scored:
        key = normalized(row['text'])
        page = (row['source'], row.get('doc'), row.get('page_course') or row.get('page_pdf'))
        if key in seen or len(by_page[page]) >= 2:
            continue
        if any((key in other or other in key) for other in by_page[page]):
            continue
        seen.add(key)
        by_page[page].append(key)
        output.append(dict(row, rank=len(output) + 1, joint_score=round(score, 6)))
        if len(output) == k:
            break
    return output


class RerankedEditorialRetriever:
    def __init__(self, index=DEFAULT_INDEX):
        self.editorial = EditorialRetriever(index)
        self.catalog = term_catalog()
        self.child_positions = {row['id']: i for i, row in enumerate(self.editorial.chunks)}
        self.coarse_vectors = {}
        self.note_pages = {}
        for path, key in [(QUALITY_RULES, 'rules'), (QUALITY_NOTES, 'notes')]:
            if path.exists():
                for entry in json.loads(path.read_text(encoding='utf-8'))[key]:
                    self.note_pages[entry['id']] = (entry['source'], entry['doc'], entry['page_pdf'])

    def vector(self, row):
        if not row['id'].startswith('legacy:'):
            return self.editorial.child_emb[self.child_positions[row['id']]]
        source = row['source']
        if source not in self.coarse_vectors:
            store = {'textbook': load_textbook, 'basic': load_basic, 'course': load_course}[source]()
            self.coarse_vectors[source] = {chunk.get('chunk_id', i): store['emb'][i]
                                           for i, chunk in enumerate(store['chunks'])}
        return self.coarse_vectors[source][row['chunk_id']]

    def retrieve(self, term, *, field='definition', k=8, pool=24, context_budget=9000, relations=False):
        if field in EXTERNAL_FIELDS:
            return external_evidence(term, field)
        if k < 1 or pool < k:
            raise ValueError('require 1 <= k <= pool')
        base = self.editorial.retrieve(term, field=field, k=pool, context_budget=0)
        target = base['term']
        aliases = [name.strip() for name in [target['zh'], target['en'], *target['aliases']] if name.strip()]
        candidate = {row['id']: dict(row, query_origin='term')
                     for row in [*base['anchor_rows'], *base['supplemental_rows']]}
        edge = related_query(target['slug'], field, self.catalog) if relations else None
        extra_audit = []
        notes = {note['finding_id']: note for note in base['external_review_notes']}
        if edge is not None:
            # The graph changes the lookup, while scoring stays on the original term.
            expanded = dict(target, aliases=[*target['aliases'], *edge['names']])
            extra = self.editorial.retrieve(expanded, field=field, k=k, context_budget=0)
            for row in [*extra['anchor_rows'], *extra['supplemental_rows']]:
                if mentions(row['text'], aliases):
                    candidate.setdefault(row['id'], dict(row, query_origin='relation'))
            extra_audit = extra['anchor_audit']
            notes.update((note['finding_id'], note) for note in extra['external_review_notes'])
        query_vectors = self.editorial.cache[tuple(base['queries'])]
        query_vectors = query_vectors / np.clip(np.linalg.norm(query_vectors, axis=1, keepdims=True), 1e-9, None)
        rows = list(candidate.values())
        similarities = np.asarray([self.vector(r) for r in rows]) @ query_vectors.T if rows else np.empty((0, 3))
        scores = 0.65 * similarities[:, 0] + 0.35 * np.max(similarities, axis=1)
        ranked = rank_evidence(rows, scores, aliases, 2 * k)
        primary = ranked[:k]
        complements = [row for row in ranked if row.get('parent_id')]
        contexts = evidence_context(primary, complements, self.editorial.pages, context_budget)
        for entry in contexts:
            if entry['context_role'] == 'coarse_anchor':
                entry['context_role'] = 'ranked_passage'
        used_pages = {(r['source'], r.get('doc'), r.get('page_course') or r.get('page_pdf')) for r in contexts}
        notes = [note for key, note in notes.items() if self.note_pages.get(key) in used_pages]
        base.update(rows=primary, supplemental_rows=complements, contexts=contexts,
                    retrieval_strategy='joint_rerank_with_relation' if relations else 'joint_rerank',
                    relation_query=edge, pool=pool, pool_candidates=len(rows),
                    relation_candidates=sum(r['query_origin'] == 'relation' for r in rows),
                    context_budget=context_budget, context_characters=sum(len(r['text']) for r in contexts),
                    retrieved_characters=sum(len(r['text']) for r in primary),
                    external_review_notes=notes, anchor_audit=base['anchor_audit'] + extra_audit)
        return base


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('term')
    parser.add_argument('--field', choices=sorted(TEXT_FIELDS | EXTERNAL_FIELDS), default='definition')
    parser.add_argument('--relations', action='store_true')
    parser.add_argument('--pool', type=int, default=24)
    parser.add_argument('--k', type=int, default=8)
    parser.add_argument('--budget', type=int, default=9000)
    parser.add_argument('--package', action='store_true')
    parser.add_argument('--diagnostics', action='store_true')
    args = parser.parse_args()
    term = resolve_term(args.term)
    result = (external_evidence(term, args.field) if args.field in EXTERNAL_FIELDS else
              RerankedEditorialRetriever().retrieve(term, field=args.field, k=args.k, pool=args.pool,
                                                    context_budget=args.budget, relations=args.relations))
    if not args.diagnostics:
        result = model_payload(result)
    if args.package:
        result = {'text_evidence': result, 'formula_evidence': external_evidence(term)}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
