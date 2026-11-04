#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""rag_multi.py —— 双源检索薄封装（教材 + 课程讲义）。

设计原则：
  * 不修改 rag_core.py 与 index.pkl；只复用其 BM25 / tokenize / embed_texts
  * 每个源内部：dense(余弦) + BM25 → RRF(k=60)
  * 跨源融合：源权重加权（教材优先，默认 textbook=1.0 / course=0.9，可配）
  * 统一返回契约：
      {source, chunk_id, doc, page_course, page_pdf, page_print,
       block_source, xref, block_type, text, sim, dense_rank, bm25_rank, rrf, score}

用法：
    from rag_multi import retrieve_multi, index_status
    rows = retrieve_multi("调节效应怎么检验", k=8)
    python rag_multi.py "调节效应怎么检验"
"""
import os
import sys
import pickle
import hashlib
import collections

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from rag_core import BM25, tokenize, embed_texts, EMBED_MODEL  # noqa: E402

TB_INDEX = os.path.join(HERE, "rag_data", "index.pkl")
CO_INDEX = os.path.join(HERE, "rag_data", "index_course.pkl")
BASIC_INDEX = os.path.join(HERE, "rag_data", "index_basic.pkl")
RRF_K = 60
SOURCE_WEIGHT = {"textbook": 1.00, "basic": 0.95, "course": 0.90}

_cache = {}


def _load(path, source):
    if source in _cache:
        return _cache[source]
    with open(path, "rb") as f:
        d = pickle.load(f)
    emb = np.asarray(d["embeddings"], dtype=np.float32)
    emb = emb / np.clip(np.linalg.norm(emb, axis=1, keepdims=True), 1e-9, None)
    _cache[source] = {
        "chunks": d["chunks"], "emb": emb, "meta": d,
        "bm25": BM25([tokenize(c["text"]) for c in d["chunks"]]),
    }
    return _cache[source]


def load_textbook():
    return _load(TB_INDEX, "textbook")


def load_course():
    return _load(CO_INDEX, "course")


def load_basic():
    return _load(BASIC_INDEX, "basic")


def _search(store, qvec, qtok, n_pool):
    emb, chunks = store["emb"], store["chunks"]
    sims = emb @ qvec
    dense_order = list(np.argsort(-sims)[:n_pool])
    bm = store["bm25"].scores(qtok)
    bm_order = list(np.argsort(-bm)[:n_pool])
    rrf = {}
    for r, i in enumerate(dense_order):
        rrf[int(i)] = rrf.get(int(i), 0.0) + 1.0 / (RRF_K + r + 1)
    for r, i in enumerate(bm_order):
        rrf[int(i)] = rrf.get(int(i), 0.0) + 1.0 / (RRF_K + r + 1)
    rank_d = {int(i): r + 1 for r, i in enumerate(dense_order)}
    rank_b = {int(i): r + 1 for r, i in enumerate(bm_order)}
    return rrf, rank_d, rank_b, sims


def _row(source, chunks, i, rrf, rank_d, rank_b, sims, weight):
    c = chunks[i]
    return {
        "source": source,
        "chunk_id": c.get("chunk_id", i),
        "doc": c.get("doc", ""),
        "page_course": c.get("page_course"),
        "page_pdf": c.get("page_pdf"),
        "page_print": c.get("page_print"),
        "block_source": c.get("block_source", ""),
        "xref": c.get("xref"),
        "block_type": c.get("block_type", ""),
        "path": c.get("path", ""),
        "chapter": c.get("chapter", c.get("chapter_title", "")),
        "text": c["text"],
        "sim": round(float(sims[i]), 4),
        "dense_rank": rank_d.get(i),
        "bm25_rank": rank_b.get(i),
        "rrf": round(float(rrf.get(i, 0.0)), 6),
        "score": round(float(rrf.get(i, 0.0)) * weight, 6),
    }


def retrieve_multi(query, k=8, sources=None, exclude_noise=True, weights=None,
                   pool_factor=10, min_pool=60):
    """多源混合检索；未指定 sources 时保持原教材+讲义双源行为。"""
    loaders = {"textbook": load_textbook, "basic": load_basic, "course": load_course}
    selected = {"textbook", "course"} if sources is None else set(sources)
    unknown = selected - set(loaders)
    if unknown:
        raise ValueError("unknown source: %s" % ", ".join(sorted(unknown)))
    w = dict(SOURCE_WEIGHT)
    if weights:
        w.update(weights)
    q = embed_texts([query])[0]
    q = q / np.linalg.norm(q)
    qtok = tokenize(query)

    out = []
    for source in ("textbook", "basic", "course"):
        if source not in selected:
            continue
        store = loaders[source]()
        chunks = store["chunks"]
        n_pool = min(len(chunks), max(k * pool_factor, min_pool))
        rrf, rank_d, rank_b, sims = _search(store, q, qtok, n_pool)
        for i in sorted(rrf, key=lambda x: -rrf[x]):
            c = chunks[i]
            if source == "textbook" and exclude_noise and c.get("block_type") == "noise":
                continue
            out.append(_row(source, chunks, i, rrf, rank_d, rank_b, sims, w[source]))
    out.sort(key=lambda r: -r["score"])
    for rank, r in enumerate(out[:k], 1):
        r["rank"] = rank
    return out[:k]


def index_status():
    """两个源的指纹与新鲜度（只读检查，不修改任何索引）。"""
    st = {}

    def _meta(path):
        if not os.path.exists(path):
            return {"exists": False}
        with open(path, "rb") as f:
            d = pickle.load(f)
        with open(path, "rb") as raw:
            index_sha = hashlib.sha256(raw.read()).hexdigest()
        return {"exists": True, "blocks": len(d["chunks"]),
                "version": d.get("version"), "embed_model": d.get("embed_model"),
                "created_at": d.get("created_at"), "sha256": index_sha}

    tb = _meta(TB_INDEX)
    if tb["exists"]:
        with open(TB_INDEX, "rb") as f:
            d = pickle.load(f)
        src = d.get("src")
        if src and os.path.exists(src):
            with open(src, "rb") as raw:
                src_sha = hashlib.sha256(raw.read()).hexdigest()
            tb["src_fresh"] = src_sha == d.get("src_sha256")
        else:
            tb["src_fresh"] = False
    st["textbook"] = tb

    co = _meta(CO_INDEX)
    if co["exists"]:
        with open(CO_INDEX, "rb") as f:
            d = pickle.load(f)
        man = os.path.join(os.path.dirname(HERE), "site", "content", "course_manifest.json")
        if os.path.exists(man):
            with open(man, "rb") as raw:
                manifest_sha = hashlib.sha256(raw.read()).hexdigest()
            co["manifest_fresh"] = manifest_sha == d.get("manifest_sha256")
        else:
            co["manifest_fresh"] = False
        co["docs"] = sorted({c.get("doc") for c in d["chunks"]})
    st["course"] = co

    basic = _meta(BASIC_INDEX)
    if basic["exists"]:
        with open(BASIC_INDEX, "rb") as f:
            d = pickle.load(f)
        src = d.get("src")
        if src and os.path.exists(src):
            with open(src, "rb") as f:
                basic["src_fresh"] = hashlib.sha256(f.read()).hexdigest() == d.get("src_sha256")
        else:
            basic["src_fresh"] = False
        basic["page_count"] = d.get("page_count")
        basic["extraction_method"] = d.get("extraction_method")
    st["basic"] = basic
    return st


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "调节效应怎么检验"
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    import json
    print(json.dumps(index_status(), ensure_ascii=False, indent=1))
    print("\nQ:", q)
    for r in retrieve_multi(q, k=k):
        loc = ("教材 p%s(PDF %s)" % (r["page_print"], r["page_pdf"])) \
            if r["source"] == "textbook" else ("讲义 %s 第%s页[%s]" %
                                               (r["doc"], r["page_course"], r["block_source"]))
        print("  #%d %-8s %-30s sim=%.4f rrf=%.5f | %s"
              % (r["rank"], r["source"], loc, r["sim"], r["rrf"],
                 r["text"][:60].replace("\n", " ")))
