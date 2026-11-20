"""Build an isolated editorial index from native PDF text and legacy OCR pages."""
from __future__ import annotations

import argparse
import collections
import datetime
import hashlib
import json
import pickle
from pathlib import Path

import numpy as np
from paths import advanced_pdf, basic_pdf, input_path

from editorial_rag import ROOT, HERE, DEFAULT_INDEX, chunk_page, clean_text, normalized, reviewed_status


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def extract_native(pdf_path):
    import pymupdf
    with pymupdf.open(pdf_path) as pdf:
        # Content-stream order preserves slide/column blocks better than global
        # y-coordinate sorting, which interleaves neighboring columns.
        return [p.get_text('text', sort=False) for p in pdf]


def build(output=DEFAULT_INDEX, audit_dir=None, target=420, maxlen=700, *,
          advanced=None, basic=None, course_manifest=None, course_pdf_dir=None):
    audit_dir = Path(audit_dir or ROOT / 'outputs/editorial-rag-local')
    audit_dir.mkdir(parents=True, exist_ok=True)
    course_manifest = Path(course_manifest or input_path('PSY_STATS_COURSE_MANIFEST', 'site/content/course_manifest.json'))
    if not course_manifest.is_file():
        raise SystemExit('Missing course manifest. See rag/README_EDITORIAL.md for local material preparation.')
    course = json.loads(course_manifest.read_text(encoding='utf-8'))
    pdfs = {('textbook', 'advanced'): Path(advanced or advanced_pdf())}
    pdf_dir = Path(course_pdf_dir or input_path('PSY_STATS_COURSE_PDF_DIR', '.'))
    pdfs.update({('course', e['slug']): pdf_dir / e['source_file'] for e in course['files']})
    legacy, vectors, manifests = [], [], []
    for source, name in [('textbook', 'index.pkl'), ('basic', 'index_basic.pkl'), ('course', 'index_course.pkl')]:
        path = HERE / 'rag_data' / name
        if not path.is_file():
            raise SystemExit(f'Missing {name}. Build the three source indexes first. See rag/README_EDITORIAL.md.')
        with path.open('rb') as handle:
            payload = pickle.load(handle)
        manifests.append({'source': source, 'file': str(path), 'sha256': digest(path), 'chunks': len(payload['chunks'])})
        vectors.append(np.asarray(payload['embeddings'], dtype=np.float32))
        if source == 'basic':
            pdfs[(source, 'basic')] = Path(basic or basic_pdf())
        for old in payload['chunks']:
            entry = dict(old, source=source, legacy_ref=source + ':' + str(old['chunk_id']))
            entry['doc'] = old.get('doc') or ('advanced' if source == 'textbook' else 'basic')
            entry['page_pdf'] = old.get('page_course') if source == 'course' else old.get('page_pdf')
            legacy.append(entry)
    by_page = collections.defaultdict(list)
    for i, chunk in enumerate(legacy):
        by_page[(chunk['source'], chunk['doc'], chunk['page_pdf'])].append((i, chunk))
    pages, parent_legacy, extraction = {}, {}, []
    for (source, doc), pdf_path in pdfs.items():
        texts = extract_native(pdf_path)
        pdf_hash = digest(pdf_path)
        extraction.append({'source': source, 'doc': doc, 'pdf': str(pdf_path), 'sha256': pdf_hash,
                           'pages': len(texts), 'nonempty_pages': sum(bool(t.strip()) for t in texts),
                           'characters': sum(map(len, texts)), 'method': 'PDF_TEXT_LAYER_content_stream_order'})
        for number, native in enumerate(texts, 1):
            prior = by_page.get((source, doc, number), [])
            variants = []
            if len(normalized(native)) >= 80:
                variants.append(('native', native))
            # Native PDF pages can contain screenshots: their old OCR remains
            # a separate evidence variant rather than being silently replaced.
            ocr_parts = [c['text'] for _, c in prior if source == 'textbook' or
                         c.get('block_source') in {'IMAGE_OCR', 'TABLE_CANDIDATE'} or not variants]
            unique, seen = [], set()
            for part in ocr_parts:
                if normalized(part) not in seen:
                    unique.append(part); seen.add(normalized(part))
            if unique:
                fallback = '\n'.join(unique)
                if not variants or normalized(fallback) != normalized(variants[0][1]):
                    method = 'legacy_ocr' if source != 'basic' else 'legacy_text_layer'
                    variants.append((method, fallback))
            for variant, text in variants:
                pid = f'{source}:{doc}:page:{number}:{variant}'
                meta = prior[0][1] if prior else {}
                body = clean_text(text)
                is_catalog = (source == 'textbook' and number >= 421) or (
                    '目录' in normalized(body[:150]) or body[:80].strip().startswith('参考文献'))
                pages[pid] = {'id': pid, 'source': source, 'doc': doc, 'page_pdf': number,
                              'page_print': meta.get('page_print'), 'method': variant,
                              'pdf_path': str(pdf_path), 'source_sha256': pdf_hash,
                              'path': meta.get('path', meta.get('chapter_title', '')),
                              'legacy_refs': [c['legacy_ref'] for _, c in prior],
                              'is_catalog': is_catalog, 'text': body}
                parent_legacy[pid] = [i for i, _ in prior]
    chunks = [c for p in pages.values() for c in chunk_page(p, target=target, maxlen=maxlen)]
    for chunk in chunks:
        chunk['quality'] = reviewed_status(chunk, pages)
    from rag_core import embed_texts
    print('Embedding candidate children:', len(chunks), flush=True)
    child_embeddings = embed_texts([c['text'] for c in chunks])
    payload = {'version': 'editorial-1.1-reviewed', 'created_at': datetime.datetime.now().isoformat(),
               'pages': pages, 'chunks': chunks, 'legacy_embeddings': np.vstack(vectors),
               'child_embeddings': child_embeddings,
               'parent_legacy': parent_legacy, 'input_manifest': manifests,
               'params': {'target': target, 'maxlen': maxlen, 'overlap': 80},
               'formula_policy': 'external_verified_only'}
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('wb') as handle:
        pickle.dump(payload, handle)
    report = {'output': str(output), 'index_sha256': digest(output), 'pages': len(pages),
              'children': len(chunks), 'status_counts': dict(collections.Counter(c['quality']['status'] for c in chunks)),
              'method_counts': dict(collections.Counter(p['method'] for p in pages.values())),
              'extraction': extraction, 'legacy_inputs': manifests,
              'new_embedding_model': False, 'dense_strategy': 'same BGE model re-embeds native/OCR sentence children; BM25 + dense RRF, separate parent context',
              'quarantined_children': [{k: c[k] for k in ['id', 'source', 'doc', 'page_pdf', 'text', 'quality']} for c in chunks if c['quality']['status'] == 'quarantined']}
    (audit_dir / 'candidate_build_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (audit_dir / 'candidate_pages.json').write_text(json.dumps(list(pages.values()), ensure_ascii=False), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in ['extraction','quarantined_children']}, ensure_ascii=False, indent=2))
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=DEFAULT_INDEX)
    parser.add_argument('--audit-dir', type=Path)
    parser.add_argument('--advanced-pdf', type=Path)
    parser.add_argument('--basic-pdf', type=Path)
    parser.add_argument('--course-manifest', type=Path)
    parser.add_argument('--course-pdf-dir', type=Path)
    args = parser.parse_args()
    build(args.out, args.audit_dir, advanced=args.advanced_pdf, basic=args.basic_pdf,
          course_manifest=args.course_manifest, course_pdf_dir=args.course_pdf_dir)
