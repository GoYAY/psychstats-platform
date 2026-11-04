# -*- coding: utf-8 -*-
"""Chunking / Metadata 审计：直接读取构建好的 index.pkl。"""
import pickle
import re
import random
import collections
import numpy as np
try:
    from .paths import rag_index
except ImportError:
    from paths import rag_index

d = pickle.load(open(rag_index(), "rb"))
chunks = d["chunks"]
print("chunks:", len(chunks), " dim:", d["embeddings"].shape)

lens = [len(c["text"]) for c in chunks]
print("len  min/mean/median/max:", min(lens), round(float(np.mean(lens)), 1),
      int(np.median(lens)), max(lens))
print("chunks <300 chars:", sum(1 for l in lens if l < 300))
print("chunks >900 chars:", sum(1 for l in lens if l > 900))

# ---- 实际重叠 ----
ov = []
for i in range(len(chunks) - 1):
    a, b = chunks[i]["text"], chunks[i + 1]["text"]
    m = 0
    for L in range(min(len(a), len(b), 400), 0, -1):
        if a[-L:] == b[:L]:
            m = L
            break
    ov.append(m)
print("overlap mean/min/max:", round(float(np.mean(ov)), 1), min(ov), max(ov))

# ---- section 元数据 ----
sec = collections.Counter(c["section"] for c in chunks)
print("\nsection 为空的 chunk 数:", sec.get("", 0), f"({sec.get('',0)/len(chunks):.1%})")
print("section 取值分布 top:", sec.most_common(12))

# ---- 页眉污染：chunk 以章节标题行开头 ----
hdr_pat = re.compile(r"^第[一二三四五六七八九十百]+章")
n_hdr = sum(1 for c in chunks if hdr_pat.match(c["text"].lstrip()))
print("\n以『第X章』开头的 chunk（页眉被吞进正文）:", n_hdr)

# ---- 页码残留 ----
num_res = re.compile(r"(?m)^\s*\d{1,3}\s*/\s*$")
n_res = sum(1 for c in chunks if num_res.search(c["text"]))
print("含『123/』页码残留的 chunk:", n_res)

# ---- 目录页污染：单个 chunk 内含大量章节名 ----
chap_pat = re.compile(r"第[一二三四五六七八九十百]+章")
multi = [(i, len(chap_pat.findall(c["text"]))) for i, c in enumerate(chunks)]
toc_like = [i for i, n in multi if n >= 6]
print("疑似目录 chunk（含>=6 个『第X章』）:", len(toc_like), toc_like[:10])

# ---- 重复 chunk ----
txts = [c["text"] for c in chunks]
dups = len(txts) - len(set(txts))
print("完全重复的 chunk 数:", dups)

# ---- 跨页情况（只能看起始页，记录页码跨度）----
pages = [c["page"] for c in chunks]
print("page 范围:", min(pages), "-", max(pages))

# ---- 随机抽样 5 个 chunk 全文 ----
random.seed(7)
print("\n########## 随机 chunk 抽样 ##########")
for i in random.sample(range(len(chunks)), 5):
    c = chunks[i]
    print(f"\n--- chunk#{i} len={len(c['text'])} page={c['page']} section='{c['section']}' ---")
    print(c["text"][:520])
