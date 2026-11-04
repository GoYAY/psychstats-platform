#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
rag_core.py  v2 —— 检索核心（混合检索 + 噪声过滤 + 版本校验 + debug 信息）

修复清单：
  [HIGH] 无 hybrid 检索 -> BM25(中文二元组+英文词) 与 dense 余弦做 RRF 融合
  [HIGH] 噪声块污染    -> 默认过滤 block_type=='noise'（可用 include_noise=True 放开）
  [HIGH] stale index   -> 校验 src_sha256 / chunk_ver / embed_model，暴露 index_status()
  [LOW]  debug 能力    -> 返回 dense_rank / bm25_rank / rrf / path / page_print 等
"""
import os
import re
import math
import pickle
import hashlib
import collections

import numpy as np

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
from fastembed import TextEmbedding  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(HERE, "rag_data", "index.pkl")
EMBED_MODEL = "BAAI/bge-small-zh-v1.5"
MODEL_DIR = os.path.join(HERE, "models", "bge-small-zh-v1.5")
EXPECTED_CHUNK_VER = "2.0"

_model = None
_index = None

WORD_RE = re.compile(r"[a-z0-9][a-z0-9_\.\-]*")
CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")


def get_model():
    global _model
    if _model is None:
        if os.path.isdir(MODEL_DIR):
            _model = TextEmbedding(model_name=EMBED_MODEL, specific_model_path=MODEL_DIR)
        else:
            _model = TextEmbedding(model_name=EMBED_MODEL)
    return _model


def embed_texts(texts):
    # parallel=None：单进程，避免每个 worker 各加载一份模型导致内存爆掉(bad allocation)
    vecs = list(get_model().embed(texts, batch_size=16, parallel=None))
    return np.asarray(vecs, dtype=np.float32)


# ---------------- BM25 ----------------
def tokenize(s):
    """中文用字符二元组（无需分词器），英文/数字用整词。"""
    s = s.lower()
    toks = [m.group(0) for m in WORD_RE.finditer(s)]
    for run in CJK_RUN_RE.findall(s):
        if len(run) == 1:
            toks.append(run)
        else:
            toks.extend(run[i:i + 2] for i in range(len(run) - 1))
    return toks


class BM25:
    def __init__(self, docs_tokens, k1=1.5, b=0.75):
        self.docs = docs_tokens
        self.N = len(docs_tokens)
        self.k1, self.b = k1, b
        self.tf = [collections.Counter(d) for d in docs_tokens]
        self.lens = [len(d) for d in docs_tokens]
        self.avg = sum(self.lens) / max(self.N, 1)
        df = collections.Counter()
        for d in docs_tokens:
            df.update(set(d))
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()}

    def scores(self, qtokens):
        out = np.zeros(self.N, dtype=np.float32)
        for t in set(qtokens):
            idf = self.idf.get(t)
            if idf is None:
                continue
            for i, tfmap in enumerate(self.tf):
                f = tfmap.get(t, 0)
                if not f:
                    continue
                denom = f + self.k1 * (1 - self.b + self.b * self.lens[i] / self.avg)
                out[i] += idf * f * (self.k1 + 1) / denom
        return out


# ---------------- 索引加载与一致性 ----------------
def load_index():
    global _index
    if _index is not None:
        return _index
    with open(INDEX_PATH, "rb") as f:
        d = pickle.load(f)
    emb = np.asarray(d["embeddings"], dtype=np.float32)
    emb = emb / np.clip(np.linalg.norm(emb, axis=1, keepdims=True), 1e-9, None)
    _index = {
        "chunks": d["chunks"],
        "emb": emb,
        "meta": {k: d.get(k) for k in
                 ("version", "embed_model", "src", "src_sha256", "created_at", "params")},
        "bm25": BM25([tokenize(c["text"]) for c in d["chunks"]]),
    }
    _index["status"] = _check_fresh(_index)
    return _index


def _check_fresh(idx):
    """检查索引是否与当前源文件/模型/切块版本一致。"""
    meta = idx["meta"]
    issues = []
    if meta.get("version") != EXPECTED_CHUNK_VER:
        issues.append(f"切块版本不一致：索引 {meta.get('version')} / 期望 {EXPECTED_CHUNK_VER}")
    if meta.get("embed_model") != EMBED_MODEL:
        issues.append(f"嵌入模型不一致：索引 {meta.get('embed_model')} / 当前 {EMBED_MODEL}")
    src = meta.get("src")
    if src and os.path.exists(src):
        with open(src, "rb") as f:
            cur = hashlib.sha256(f.read()).hexdigest()
        if meta.get("src_sha256") and cur != meta["src_sha256"]:
            issues.append("源 TXT 已变更（哈希不一致），索引可能过期")
    elif src:
        issues.append(f"找不到源 TXT：{src}")
    return {"fresh": not issues, "issues": issues}


def index_status():
    idx = load_index()
    st = dict(idx["status"])
    st.update(idx["meta"])
    st["blocks"] = len(idx["chunks"])
    return st


# ---------------- 检索 ----------------
def retrieve(query, k=6, mode="hybrid", include_noise=False):
    """混合检索。返回 [{rank, score, sim, dense_rank, bm25_rank, page_print, page_pdf,
                       path, chapter_no, section_no, block_type, text, ...}]"""
    idx = load_index()
    chunks, emb = idx["chunks"], idx["emb"]

    q = embed_texts([query])[0]
    q = q / np.linalg.norm(q)
    sims = emb @ q
    n_pool = min(len(chunks), max(k * 10, 60))
    dense_order = list(np.argsort(-sims)[:n_pool])

    if mode == "dense":
        order = dense_order
        scores = {int(i): float(sims[i]) for i in order}
    else:
        bm = idx["bm25"].scores(tokenize(query))
        bm_order = list(np.argsort(-bm)[:n_pool])
        rrf = {}
        for r, i in enumerate(dense_order):
            rrf[int(i)] = rrf.get(int(i), 0.0) + 1.0 / (60 + r + 1)
        for r, i in enumerate(bm_order):
            rrf[int(i)] = rrf.get(int(i), 0.0) + 1.0 / (60 + r + 1)
        order = sorted(rrf.keys(), key=lambda i: -rrf[i])
        scores = rrf

    dense_rank = {int(i): r + 1 for r, i in enumerate(dense_order)}
    if mode != "dense":
        bm = idx["bm25"].scores(tokenize(query))
        bm_order = list(np.argsort(-bm)[:n_pool])
        bm_rank = {int(i): r + 1 for r, i in enumerate(bm_order)}
    else:
        bm_rank = {}

    out = []
    for i in order:
        c = chunks[i]
        # 只过滤纯表格/数字噪声；front(目录/前言) 与 back(参考文献) 保留：
        # 实测过滤它们会让「第X章讲什么」这类章级查询 Recall@10 归零（目录是唯一强信号）
        if c.get("block_type") == "noise" and not include_noise:
            continue
        item = {
            "rank": len(out) + 1,
            "score": round(float(scores.get(i, 0.0)), 5),
            "sim": round(float(sims[i]), 4),
            "dense_rank": dense_rank.get(i),
            "bm25_rank": bm_rank.get(i),
            "page_print": c.get("page_print", c.get("page")),
            "page_pdf": c.get("page_pdf", c.get("page")),
            "page": c.get("page_print", c.get("page")),   # 兼容旧字段：默认给印刷页
            "path": c.get("path", ""),
            "chapter_no": c.get("chapter_no", ""),
            "section_no": c.get("section_no", ""),
            "section": c.get("section_no") or c.get("chapter_no", ""),
            "block_type": c.get("block_type", "prose"),
            "chunk_id": c.get("chunk_id"),
            "text": c["text"],
        }
        out.append(item)
        if len(out) >= k:
            break
    return out
